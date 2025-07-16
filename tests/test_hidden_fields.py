import re

def test_index_has_single_training_id_field(client, app_instance, sample_data):
    resp = client.get('/')
    html = resp.data.decode()
    assert len(re.findall(r'id="training_id"', html)) == 1


def test_cancel_has_single_training_id_field(client, app_instance, sample_data):
    training_id, _, _, _ = sample_data
    resp = client.get(f'/cancel?training_id={training_id}')
    html = resp.data.decode()
    assert len(re.findall(r'id="training_id"', html)) == 1


def test_settings_has_single_template_fields(client, app_instance):
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    resp = client.get('/admin/settings')
    html = resp.data.decode()
    assert len(re.findall(r'id="registration_template"', html)) == 1
    assert len(re.findall(r'id="cancellation_template"', html)) == 1
