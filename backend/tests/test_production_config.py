"""Gate 11: production refuses to start with insecure local defaults."""
from app.core.config import Settings, check_production_settings


def test_dev_defaults_are_rejected_for_production():
    problems = check_production_settings(Settings(_env_file=None))
    joined = " ".join(problems)
    assert "JWT_SECRET" in joined
    assert "MONGO_URI" in joined
    assert "FRONTEND_URL" in joined


def test_a_complete_production_config_passes():
    s = Settings(
        _env_file=None,
        JWT_SECRET="x" * 48,
        MONGO_URI="mongodb+srv://u:p@cluster0.example.mongodb.net",
        GOOGLE_API_KEY="real-key",
        GMAIL_MCP_CLIENT_ID="id.apps.googleusercontent.com",
        TOKEN_ENCRYPTION_KEY="k" * 44,
        GMAIL_OAUTH_REDIRECT_URI="https://pathlight-api.onrender.com/api/integrations/gmail/callback",
        FRONTEND_URL="https://pathlight.vercel.app",
    )
    assert check_production_settings(s) == []
