"""WhatsApp test-recipient redirect."""

from unittest.mock import patch


def test_whatsapp_test_redirect_uses_owner_phone(app_instance):
    from app.whatsapp_utils import send_whatsapp_message, whatsapp_test_recipient

    with app_instance.app_context():
        app_instance.config["WHATSAPP_API_URL"] = "http://waha:3000"
        app_instance.config["WHATSAPP_TEST_PHONE"] = "+48697495755"

        with patch("app.whatsapp_utils.requests.post") as post:
            post.return_value.status_code = 201
            post.return_value.text = "ok"
            with whatsapp_test_recipient(True):
                ok, err = send_whatsapp_message("+48500111222", "hello")

        assert ok and err is None
        payload = post.call_args.kwargs["json"]
        assert payload["chatId"] == "48697495755@c.us"
        assert "[TEST — oryginalnie dla: +48500111222]" in payload["text"]


def test_whatsapp_without_test_mode_keeps_target(app_instance):
    from app.whatsapp_utils import send_whatsapp_message

    with app_instance.app_context():
        app_instance.config["WHATSAPP_API_URL"] = "http://waha:3000"

        with patch("app.whatsapp_utils.requests.post") as post:
            post.return_value.status_code = 201
            post.return_value.text = "ok"
            ok, err = send_whatsapp_message("+48500111222", "hello")

        assert ok and err is None
        assert post.call_args.kwargs["json"]["chatId"] == "48500111222@c.us"
