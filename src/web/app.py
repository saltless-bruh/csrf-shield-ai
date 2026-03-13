"""Flask Web Dashboard for CSRF Shield AI.

Provides an optional browser-based UI to upload HAR files, run the ML pipeline,
and view the analysis results and visual dashboards.

Ref:
    - docs/proposal/PROPOSAL.md §5 (Phase 5)
    - spec/Tasks.md T-511, T-512, T-513
"""

import os
from pathlib import Path
from typing import Union
from flask import (
    Flask, request, render_template, redirect, url_for, flash, jsonify
)
from werkzeug.wrappers import Response
from werkzeug.utils import secure_filename

from src.input.har_parser import parse_har_file
from src.input.flow_reconstructor import reconstruct_flows
from src.input.auth_detector import update_flow_auth
from src.pipeline import CsrfPipeline

app = Flask(
    __name__, template_folder='../../templates', static_folder='static'
)
app.secret_key = 'csrf-shield-ai-secret'  # Safe for local dev server
UPLOAD_FOLDER = '/tmp/csrf_shield_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit

pipeline = None  # Lazy loaded


def get_pipeline() -> CsrfPipeline:
    global pipeline
    if pipeline is None:
        pipeline = CsrfPipeline()
    return pipeline


@app.route('/', methods=['GET', 'POST'])
def index() -> Union[Response, str]:
    if request.method == 'POST':
        if 'har_file' not in request.files:
            flash('No file uploaded.')
            return redirect(request.url)

        file = request.files['har_file']
        if not file.filename:
            flash('No file selected.')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        if file and filename.endswith('.har'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            return redirect(url_for('analyze', filename=filename))

        flash('Invalid file format. Please upload a .har file.')
        return redirect(request.url)

    return render_template('dashboard_index.html')


@app.route('/analyze/<filename>')
def analyze(filename: str) -> Union[Response, str]:
    filepath = Path(app.config['UPLOAD_FOLDER']) / secure_filename(filename)
    if not filepath.exists():
        flash('File not found.')
        return redirect(url_for('index'))

    try:
        exchanges = parse_har_file(filepath)
        raw_flows = reconstruct_flows(exchanges)
        flows = [update_flow_auth(f) for f in raw_flows]

        # Analyze first flow for simplicity in demo
        if not flows:
            flash('No valid user sessions/flows found in HAR file.')
            return redirect(url_for('index'))

        p = get_pipeline()
        flow = flows[0]  # Dashboard demo currently evaluates primary session
        result = p._analyze_flow(flow)

        return render_template(
            'dashboard_results.html',
            filename=filename,
            result=result,
            exchange_count=len(flow.exchanges)
        )
    except Exception as e:
        flash(f'Analysis failed: {str(e)}')
        return redirect(url_for('index'))


@app.route('/api/health')
def health() -> Response:
    return jsonify({
        "status": "ok",
        "message": "CSRF Shield Web Dashboard Running"
    })


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
