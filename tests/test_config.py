from app.config import Settings


def test_mcp_server_url_accepts_internal_docker_service():
    settings = Settings(
        mcp_server_url="http://mcp:8001/mcp",
        _env_file=None,
    )
    assert settings.mcp_server_url == "http://mcp:8001/mcp"


def test_mcp_server_url_rejects_arbitrary_plain_http():
    try:
        Settings(
            mcp_server_url="http://example.com/mcp",
            _env_file=None,
        )
    except ValueError as error:
        assert "MCP_SERVER_URL" in str(error)
    else:
        raise AssertionError("Une URL HTTP publique ne doit pas être acceptée.")
