"""Test Api class"""

from unittest import mock

import pytest

from flask import jsonify
from flask.views import MethodView
from werkzeug.routing import BaseConverter
import marshmallow as ma
import apispec

from flask_rest_api import Api, Blueprint
from flask_rest_api.exceptions import OpenAPIVersionNotSpecified

from .utils import get_definitions


class TestApi():
    """Test Api class"""

    def test_api_definition(self, app, schemas):
        DocSchema = schemas.DocSchema
        api = Api(app)
        with mock.patch.object(apispec.core.Components, 'schema') as mock_def:
            ret = api.definition('Document')(DocSchema)
        assert ret is DocSchema
        mock_def.assert_called_once_with('Document', schema=DocSchema)

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    def test_api_definition_before_and_after_init(self, app, openapi_version):
        app.config['OPENAPI_VERSION'] = openapi_version
        api = Api()

        @api.definition('Schema_1')
        class Schema_1(ma.Schema):
            int_1 = ma.fields.Int()

        api.init_app(app)

        @api.definition('Schema_2')
        class Schema_2(ma.Schema):
            int_2 = ma.fields.Int()

        definitions = get_definitions(api.spec)
        assert {'Schema_1', 'Schema_2'}.issubset(definitions)

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    @pytest.mark.parametrize('view_type', ['function', 'method'])
    @pytest.mark.parametrize('custom_format', ['custom', None])
    def test_api_register_converter(
            self, app, view_type, custom_format, openapi_version):
        api = Api(app)
        blp = Blueprint('test', 'test', url_prefix='/test')

        class CustomConverter(BaseConverter):
            pass

        app.url_map.converters['custom_str'] = CustomConverter
        api.register_converter(CustomConverter, 'custom string', custom_format)

        if view_type == 'function':
            @blp.route('/<custom_str:val>')
            def test_func(val):
                return jsonify(val)
        else:
            @blp.route('/<custom_str:val>')
            class TestMethod(MethodView):
                def get(self, val):
                    return jsonify(val)

        api.register_blueprint(blp)
        spec = api.spec.to_dict()

        schema = {'type': 'custom string'}
        # If custom_format is None (default), it does not appear in the spec
        if custom_format is not None:
            schema['format'] = 'custom'
        parameter = {'in': 'path', 'name': 'val', 'required': True}
        if 'openapi_version' == '2.0':
            parameter.update(schema)
        else:
            parameter['schema'] = schema
        assert spec['paths']['/test/{val}']['get']['parameters'] == [parameter]

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    def test_api_register_converter_before_and_after_init(
            self, app, openapi_version):
        api = Api()
        blp = Blueprint('test', 'test', url_prefix='/test')

        class CustomConverter_1(BaseConverter):
            pass

        class CustomConverter_2(BaseConverter):
            pass

        app.url_map.converters['custom_str_1'] = CustomConverter_1
        app.url_map.converters['custom_str_2'] = CustomConverter_2
        api.register_converter(CustomConverter_1, 'custom string 1')
        api.init_app(app)
        api.register_converter(CustomConverter_2, 'custom string 2')

        @blp.route('/1/<custom_str_1:val>')
        def test_func_1(val):
            return jsonify(val)

        @blp.route('/2/<custom_str_2:val>')
        def test_func_2(val):
            return jsonify(val)

        api.register_blueprint(blp)
        spec = api.spec.to_dict()
        parameter_1 = spec['paths']['/test/1/{val}']['get']['parameters'][0]
        parameter_2 = spec['paths']['/test/2/{val}']['get']['parameters'][0]
        if 'openapi_version' == '2.0':
            assert parameter_1['type'] == 'custom string 1'
            assert parameter_2['type'] == 'custom string 2'
        else:
            assert parameter_1['schema']['type'] == 'custom string 1'
            assert parameter_2['schema']['type'] == 'custom string 2'

    @pytest.mark.parametrize('mapping', [
        ('custom string', 'custom'),
        ('custom string', None),
        (ma.fields.Integer, ),
    ])
    def test_api_register_field(self, app, mapping):
        api = Api(app)

        class CustomField(ma.fields.Field):
            pass

        api.register_field(CustomField, *mapping)

        @api.definition('Document')
        class Document(ma.Schema):
            field = CustomField()

        if len(mapping) == 2:
            properties = {'field': {'type': 'custom string'}}
            # If mapping format is None, it does not appear in the spec
            if mapping[1] is not None:
                properties['field']['format'] = mapping[1]
        else:
            properties = {'field': {'type': 'integer', 'format': 'int32'}}

        assert get_definitions(api.spec)['Document'] == {
            'properties': properties, 'type': 'object'}

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    def test_api_register_field_before_and_after_init(
            self, app, openapi_version):
        app.config['OPENAPI_VERSION'] = openapi_version
        api = Api()

        class CustomField_1(ma.fields.Field):
            pass

        class CustomField_2(ma.fields.Field):
            pass

        api.register_field(CustomField_1, 'custom string', 'custom')

        @api.definition('Schema_1')
        class Schema_1(ma.Schema):
            int_1 = ma.fields.Int()
            custom_1 = CustomField_1()

        api.init_app(app)
        api.register_field(CustomField_2, 'custom string', 'custom')

        @api.definition('Schema_2')
        class Schema_2(ma.Schema):
            int_2 = ma.fields.Int()
            custom_2 = CustomField_2()

        definitions = get_definitions(api.spec)
        assert definitions['Schema_1']['properties']['custom_1'] == {
            'type': 'custom string', 'format': 'custom'}
        assert definitions['Schema_2']['properties']['custom_2'] == {
            'type': 'custom string', 'format': 'custom'}

    def test_api_extra_spec_kwargs(self, app):
        """Test APISpec kwargs can be passed in Api init or app config"""
        app.config['API_SPEC_OPTIONS'] = {'basePath': '/v2'}
        api = Api(app, spec_kwargs={'basePath': '/v1', 'host': 'example.com'})
        spec = api.spec.to_dict()
        assert spec['host'] == 'example.com'
        # app config overrides Api spec_kwargs parameters
        assert spec['basePath'] == '/v2'

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    def test_api_extra_spec_plugins(self, app, schemas, openapi_version):
        """Test extra plugins can be passed to internal APISpec instance"""
        app.config['OPENAPI_VERSION'] = openapi_version

        class MyPlugin(apispec.BasePlugin):
            def schema_helper(self, name, definition, **kwargs):
                return {'dummy': 'whatever'}

        api = Api(app, spec_kwargs={'extra_plugins': (MyPlugin(), )})
        api.definition('Pet')(schemas.DocSchema)
        assert get_definitions(api.spec)['Pet']['dummy'] == 'whatever'

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    def test_api_gets_apispec_parameters_from_app(self, app, openapi_version):
        app.config['API_VERSION'] = 'v42'
        app.config['OPENAPI_VERSION'] = openapi_version
        api = Api(app)
        spec = api.spec.to_dict()

        assert spec['info'] == {'title': 'API Test', 'version': 'v42'}
        if openapi_version == '2.0':
            assert spec['swagger'] == '2.0'
        else:
            assert spec['openapi'] == '3.0.2'

    def test_api_register_blueprint_options(self, app):
        api = Api(app)
        blp = Blueprint('test', 'test', url_prefix='/test1')

        @blp.route('/')
        def test_func():
            return jsonify('OK')

        api.register_blueprint(blp, url_prefix='/test2')

        spec = api.spec.to_dict()
        assert '/test1/' not in spec['paths']
        assert '/test2/' in spec['paths']

        client = app.test_client()
        response = client.get('/test1/')
        assert response.status_code == 404
        response = client.get('/test2/')
        assert response.status_code == 200
        assert response.json == 'OK'

    @pytest.mark.parametrize('openapi_version', ['2.0', '3.0.2'])
    @pytest.mark.parametrize('base_path', [None, '/', '/v1'])
    def test_api_apispec_sets_base_path(self, app, openapi_version, base_path):
        app.config['OPENAPI_VERSION'] = openapi_version
        if base_path is not None:
            app.config['APPLICATION_ROOT'] = base_path
        api = Api(app)
        spec = api.spec.to_dict()

        if openapi_version == '2.0':
            assert spec['basePath'] == base_path or '/'
        else:
            assert 'basePath' not in spec

    def test_api_openapi_version_parameters(self, app):
        """Test OpenAPI version must be passed, as app param or spec kwarg"""

        app.config['OPENAPI_VERSION'] = '3.0.2'
        api = Api(app)
        assert api.spec.to_dict()['openapi'] == '3.0.2'

        del app.config['OPENAPI_VERSION']
        api = Api(app, spec_kwargs={'openapi_version': '3.0.2'})
        assert api.spec.to_dict()['openapi'] == '3.0.2'

        with pytest.raises(
                OpenAPIVersionNotSpecified,
                match='The OpenAPI version must be specified'
        ):
            Api(app)
