from pandoraspec.seed import SeedManager
from unittest.mock import MagicMock, patch

class TestSeedManager:
    def test_apply_seed_data_flat(self):
        seed_data = {"user_id": 123}
        manager = SeedManager(seed_data)
        
        mock_case = MagicMock()
        mock_case.path_parameters = {"user_id": "original"}
        mock_case.query = {}
        mock_case.headers = {}
        
        manager.apply_seed_data(mock_case)
        assert mock_case.path_parameters["user_id"] == 123

    def test_apply_seed_data_hierarchical(self):
        seed_data = {
            "general": {"general_param": "gen"},
            "verbs": {
                "GET": {"verb_param": "get_val"}
            },
            "endpoints": {
                "/users": {
                    "GET": {"endpoint_param": "end_val"}
                }
            }
        }
        manager = SeedManager(seed_data)
        
        mock_case = MagicMock()
        mock_case.operation.method.upper.return_value = "GET"
        mock_case.operation.path = "/users"
        mock_case.path_parameters = {"general_param": "", "verb_param": "", "endpoint_param": ""}
        
        manager.apply_seed_data(mock_case)
        
        assert mock_case.path_parameters["general_param"] == "gen"
        assert mock_case.path_parameters["verb_param"] == "get_val"
        assert mock_case.path_parameters["endpoint_param"] == "end_val"

    @patch("requests.request")
    def test_resolve_dynamic_value(self, mock_request):
        seed_data = {}
        manager = SeedManager(seed_data, base_url="http://test.com")
        
        # Mock successful response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 999}
        mock_request.return_value = mock_resp

        config = {
            "from_endpoint": "GET /setup",
            "extract": "id"
        }
        
        val = manager._resolve_dynamic_value(config)
        assert val == 999
        mock_request.assert_called_with("GET", "http://test.com/setup", headers={}, params={})

    def test_resolve_dynamic_value_cache(self):
        manager = SeedManager({})
        manager.dynamic_cache["GET /cached"] = "cached_val"
        
        config = {"from_endpoint": "GET /cached"}
        val = manager._resolve_dynamic_value(config)
        assert val == "cached_val"
