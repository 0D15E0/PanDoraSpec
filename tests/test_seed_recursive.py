import responses
from pandoraspec.seed import SeedManager

SEED_CONFIG = {
    "endpoints": {
        "/auth/login": {
            "POST": {
                "username": "admin",
                "password": "password123"
            }
        },
        "/users": {
            "GET": {
                "token": {
                    "from_endpoint": "POST /auth/login",
                    "extract": "access_token"
                }
            }
        },
        "/users/{user_id}/details": {
            "GET": {
                "user_id": {
                    "from_endpoint": "GET /users",
                    "extract": "data.0.id",
                    "regex": "user_([0-9]+)"
                }
            }
        },
        "/cycle/a": {
            "GET": {
                "val": {"from_endpoint": "GET /cycle/b"}
            }
        },
        "/cycle/b": {
            "GET": {
                "val": {"from_endpoint": "GET /cycle/a"}
            }
        }
    }
}

class TestSeedRecursion:
    @responses.activate
    def test_recursive_resolution_chain_A_B_C(self):
        """
        Scenario:
        1. /users/{user_id}/details NEEDS 'user_id' -> calls GET /users
        2. GET /users NEEDS 'token' -> calls POST /auth/login
        3. POST /auth/login uses static seeds (username/password)
        """
        base_url = "http://api.example.com"
        manager = SeedManager(SEED_CONFIG, base_url=base_url)

        # Mock Level 1: Auth Login
        responses.add(
            responses.POST,
            "http://api.example.com/auth/login",
            json={"access_token": "valid-token-123"},
            status=200
        )

        # Mock Level 2: Get Users (needs token from Level 1)
        # We verify that the token was correctly injected into the query params
        # (Since it wasn't a path param, our logic puts it in query params currently)
        responses.add(
            responses.GET,
            "http://api.example.com/users",
            json={"data": [{"id": "user_999"}]},
            status=200,
            match=[responses.matchers.query_param_matcher({"token": "valid-token-123"})]
        )

        # Mock Level 3: The actual dynamic call we are making
        # We are testing _resolve_dynamic_value directly for 'user_id'
        
        user_id_config = SEED_CONFIG["endpoints"]["/users/{user_id}/details"]["GET"]["user_id"]
        
        # ACT
        result = manager._resolve_dynamic_value(user_id_config)

        # ASSERT
        assert len(responses.calls) == 2
        
        # Check Call 1: Login
        # Note: SeedManager sends unused params as query params by default
        assert "http://api.example.com/auth/login" in responses.calls[0].request.url
        assert "username=admin" in responses.calls[0].request.url
        assert "password=password123" in responses.calls[0].request.url
        
        # Check Call 2: Users (with token)
        assert responses.calls[1].request.url == "http://api.example.com/users?token=valid-token-123"
        
        # Check Result (extracted and regex matched)
        # "user_999" -> regex "user_([0-9]+)" -> group 1 is "999"
        assert result == "999"

    def test_cycle_detection(self):
        """
        Scenario:
        A depends on B, B depends on A.
        Should detect cycle and return None safely without crashing.
        """
        base_url = "http://api.example.com"
        manager = SeedManager(SEED_CONFIG, base_url=base_url)
        
        config_a = SEED_CONFIG["endpoints"]["/cycle/a"]["GET"]["val"]
        
        # ACT
        result = manager._resolve_dynamic_value(config_a)
        
        # ASSERT
        assert result is None
        # Should print a warning (captured logs check could be added if needed)

