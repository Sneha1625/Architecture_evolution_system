from pathlib import Path

from architecture_model.runtime_version_runner import (
    _common_runtime_entrypoint,
    _create_automatic_flask_test_client_workload,
    discover_python_entrypoints,
)


FLASK_APP = """from flask import Flask, request, render_template
from sentiment_analysis import get_sentiment

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        text = request.form['text']
        sentiment = get_sentiment(text)
        return render_template('index.html', sentiment=sentiment)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
"""


def _make_flask_project(root: Path):
    (root / 'templates').mkdir(parents=True)
    (root / 'app.py').write_text(FLASK_APP, encoding='utf-8')
    (root / 'templates' / 'index.html').write_text(
        '<html><body>{{ sentiment }}</body></html>', encoding='utf-8'
    )


def test_flask_server_is_discovered_as_bounded_test_client_workload(tmp_path):
    _make_flask_project(tmp_path)

    assert 'flask:test-client' in discover_python_entrypoints(tmp_path)


def test_common_flask_workload_is_selected_for_both_versions(tmp_path):
    v1 = tmp_path / 'v1'
    v2 = tmp_path / 'v2'
    v1.mkdir()
    v2.mkdir()
    _make_flask_project(v1)
    _make_flask_project(v2)

    assert _common_runtime_entrypoint(v1, v2) == 'flask:test-client'


def test_generated_flask_workload_uses_in_process_client_and_stubbed_api(tmp_path):
    v1 = tmp_path / 'v1'
    v2 = tmp_path / 'v2'
    v1.mkdir()
    v2.mkdir()
    _make_flask_project(v1)
    _make_flask_project(v2)

    workload = Path(_create_automatic_flask_test_client_workload(v1, v2, tmp_path))
    source = workload.read_text(encoding='utf-8')

    assert 'app.test_client()' in source
    assert "client.get('/')" in source
    assert "client.post('/', data={'text': 'runtime comparison test'})" in source
    assert 'urllib.request.urlopen = _runtime_urlopen' in source
    assert 'app.run(' not in source
