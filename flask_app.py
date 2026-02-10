"""
Flask Excel Data Visualizer
A web app that reads any Excel file and displays interactive charts.
"""

from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import re
import requests
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from io import StringIO

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    # Get data from session if available
    df = None
    current_filename = None
    has_data = False
    error = None
    
    if 'df_data' in session and 'filename' in session:
        try:
            # Reconstruct DataFrame from session
            df = pd.read_json(session['df_data'])
            current_filename = session['filename']
            has_data = True
        except Exception as e:
            error = str(e)
            session.pop('df_data', None)
            session.pop('filename', None)
    
    # Get recent uploads from session and format time
    recent_uploads = session.get('recent_uploads', [])
    now = datetime.now()
    for upload in recent_uploads:
        upload_time = datetime.fromisoformat(upload['upload_time'])
        time_diff = now - upload_time
        if time_diff.total_seconds() < 3600:
            upload['time_ago'] = f"{int(time_diff.total_seconds() / 60)} minutes ago"
        elif time_diff.total_seconds() < 86400:
            upload['time_ago'] = f"{int(time_diff.total_seconds() / 3600)} hours ago"
        else:
            upload['time_ago'] = f"{int(time_diff.total_seconds() / 86400)} days ago"
        upload['file_size_mb'] = f"{upload['file_size'] / 1024 / 1024:.1f}"
    
    if has_data and df is not None:
        # Prepare data for template
        columns = df.columns.tolist()
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        # Convert DataFrame to HTML for display with index for row numbers
        data_html = df.head(100).to_html(
            classes='min-w-full divide-y divide-gray-200', 
            table_id='data-table', 
            escape=False,
            index=True,
            border=0
        )
        
        return render_template('index.html',
                             has_data=True,
                             current_filename=current_filename,
                             columns=columns,
                             numeric_cols=numeric_cols,
                             categorical_cols=categorical_cols,
                             total_rows=len(df),
                             total_columns=len(columns),
                             numeric_columns=len(numeric_cols),
                             data_html=data_html,
                             recent_uploads=recent_uploads)
    else:
        return render_template('index.html',
                             has_data=False,
                             current_filename=None,
                             error=error,
                             recent_uploads=recent_uploads)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            
            # Get file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset file pointer
            
            # Read file based on extension
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Store in session (convert to JSON for storage)
            session['df_data'] = df.to_json()
            session['filename'] = filename
            
            # Track recent uploads
            if 'recent_uploads' not in session:
                session['recent_uploads'] = []
            
            # Add this upload to recent uploads
            now = datetime.now()
            upload_info = {
                'filename': filename,
                'upload_time': now.isoformat(),
                'upload_timestamp': now.timestamp(),
                'file_size': file_size,
                'row_count': len(df),
                'column_count': len(df.columns),
                'numeric_columns': len(df.select_dtypes(include=['number']).columns),
                'is_excel': filename.endswith('.xlsx') or filename.endswith('.xls')
            }
            
            # Remove if already exists (to avoid duplicates)
            session['recent_uploads'] = [u for u in session['recent_uploads'] if u['filename'] != filename]
            
            # Add to beginning of list
            session['recent_uploads'].insert(0, upload_info)
            
            # Keep only last 10 uploads
            session['recent_uploads'] = session['recent_uploads'][:10]
            
            return jsonify({'success': True, 'message': 'File uploaded successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Invalid file type'}), 400

@app.route('/reset', methods=['POST'])
def reset():
    session.pop('df_data', None)
    session.pop('filename', None)
    return jsonify({'success': True})

@app.route('/import-google-sheet', methods=['POST'])
def import_google_sheet():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'message': 'No URL provided'}), 400
        
        # Validate it's a Google Sheets URL
        if 'docs.google.com/spreadsheets' not in url:
            return jsonify({'success': False, 'message': 'Invalid Google Sheets URL. Must contain docs.google.com/spreadsheets'}), 400
        
        # Extract sheet ID from URL
        # Pattern: /spreadsheets/d/{SHEET_ID}/
        sheet_id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
        if not sheet_id_match:
            return jsonify({'success': False, 'message': 'Could not extract sheet ID from URL'}), 400
        
        sheet_id = sheet_id_match.group(1)
        
        # Extract GID if present (for specific sheet tab)
        gid_match = re.search(r'[#&]gid=(\d+)', url)
        gid = gid_match.group(1) if gid_match else '0'
        
        # Use the export URL format for Google Sheets
        # This works when the sheet is shared with "Anyone with the link can view"
        csv_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
        
        # Create a session to handle cookies and maintain connection
        session = requests.Session()
        
        # Headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/csv,text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f'https://docs.google.com/spreadsheets/d/{sheet_id}/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        # Download the CSV
        response = None
        try:
            # First, try to access the sheet view page to establish session
            view_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/view'
            session.get(view_url, headers=headers, timeout=10, allow_redirects=True)
            
            # Now try to download the CSV
            response = session.get(csv_url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Check if we got HTML instead of CSV (usually means authentication/access failed)
            content_type = response.headers.get('Content-Type', '').lower()
            response_text = response.text.strip() if response.text else ''
            
            # Check for HTML responses
            if 'text/html' in content_type or response_text.startswith('<!DOCTYPE') or response_text.startswith('<html') or (response_text and '<html' in response_text[:200]):
                # Try without session as fallback
                response = requests.get(csv_url, headers=headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '').lower()
                response_text = response.text.strip() if response.text else ''
                
                if 'text/html' in content_type or response_text.startswith('<!DOCTYPE') or response_text.startswith('<html') or (response_text and '<html' in response_text[:200]):
                    return jsonify({
                        'success': False, 
                        'message': 'Unable to access the sheet. Please verify:\n\n1. The sheet is shared with "Anyone with the link can view"\n   - Click the "Share" button in Google Sheets\n   - Under "General access", select "Anyone with the link"\n   - Make sure it says "Viewer" (not "Editor")\n   - Click "Done"\n\n2. Try copying the sharing link again after updating permissions\n\n3. Make sure you\'re using the full Google Sheets URL (not a shortened link)'
                    }), 400
                
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 'unknown'
            if status_code == 403:
                return jsonify({
                    'success': False,
                    'message': 'Access denied (403). The sheet is not accessible. Please:\n\n1. Open your Google Sheet\n2. Click the "Share" button\n3. Under "General access", change to "Anyone with the link"\n4. Make sure the permission is set to "Viewer"\n5. Click "Done"\n6. Try again with the same URL'
                }), 400
            elif status_code == 400:
                return jsonify({
                    'success': False,
                    'message': 'Bad request (400). Please verify:\n\n1. The sheet is shared with "Anyone with the link can view"\n2. You\'re using the correct Google Sheets URL\n3. The sheet is not empty\n\nIf the problem persists, try:\n- Opening the sheet in your browser first\n- Then copying the URL from the address bar'
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'message': f'Error downloading sheet (HTTP {status_code}). Please make sure:\n\n1. The sheet is shared with "Anyone with the link can view"\n2. The URL is correct and accessible\n3. Try opening the sheet in your browser to verify it\'s accessible'
                }), 400
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            return jsonify({
                'success': False,
                'message': f'Error downloading sheet: {error_msg}\n\nPlease verify:\n1. The sheet is shared with "Anyone with the link can view"\n2. Your internet connection is working\n3. The Google Sheets URL is correct'
            }), 400
        finally:
            session.close()
        
        # Verify we have a valid response
        if not response or not response.text:
            return jsonify({'success': False, 'message': 'No data received from Google Sheets. Please verify the sheet is accessible and try again.'}), 400
        
        # Read CSV into DataFrame
        try:
            df = pd.read_csv(StringIO(response.text))
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error parsing CSV data: {str(e)}'}), 400
        
        if df.empty:
            return jsonify({'success': False, 'message': 'The sheet appears to be empty'}), 400
        
        # Store in session (convert to JSON for storage)
        session['df_data'] = df.to_json()
        session['filename'] = f'Google Sheet ({sheet_id[:8]}...)'
        
        # Track recent uploads
        if 'recent_uploads' not in session:
            session['recent_uploads'] = []
        
        # Add this upload to recent uploads
        now = datetime.now()
        upload_info = {
            'filename': f'Google Sheet ({sheet_id[:8]}...)',
            'upload_time': now.isoformat(),
            'upload_timestamp': now.timestamp(),
            'file_size': len(response.text.encode('utf-8')),
            'row_count': len(df),
            'column_count': len(df.columns),
            'numeric_columns': len(df.select_dtypes(include=['number']).columns),
            'is_excel': False
        }
        
        # Remove if already exists (to avoid duplicates)
        session['recent_uploads'] = [u for u in session['recent_uploads'] if u['filename'] != upload_info['filename']]
        
        # Add to beginning of list
        session['recent_uploads'].insert(0, upload_info)
        
        # Keep only last 10 uploads
        session['recent_uploads'] = session['recent_uploads'][:10]
        
        return jsonify({'success': True, 'message': 'Google Sheet imported successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error importing Google Sheet: {str(e)}'}), 500

@app.route('/chart/bar', methods=['POST'])
def get_bar_chart():
    if 'df_data' not in session:
        return jsonify({'error': 'No data available'}), 400
    
    try:
        data = request.get_json()
        x_col = data.get('x_col')
        y_col = data.get('y_col')
        
        df = pd.read_json(session['df_data'])
        
        fig = px.bar(
            df,
            x=x_col,
            y=y_col,
            title=f"{y_col} by {x_col}",
            labels={x_col: x_col, y_col: y_col},
            color_discrete_sequence=['#3B82F6']
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chart/line', methods=['POST'])
def get_line_chart():
    if 'df_data' not in session:
        return jsonify({'error': 'No data available'}), 400
    
    try:
        data = request.get_json()
        line_col = data.get('line_col')
        
        df = pd.read_json(session['df_data'])
        
        fig = px.line(
            df,
            y=line_col,
            title=f"{line_col} Over Time",
            labels={'index': 'Index', line_col: line_col},
            color_discrete_sequence=['#3B82F6']
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chart/pie', methods=['POST'])
def get_pie_chart():
    if 'df_data' not in session:
        return jsonify({'error': 'No data available'}), 400
    
    try:
        data = request.get_json()
        cat_col = data.get('cat_col')
        val_col = data.get('val_col')
        
        df = pd.read_json(session['df_data'])
        
        # Group by category and sum values
        pie_data = df.groupby(cat_col)[val_col].sum().reset_index()
        
        fig = px.pie(
            pie_data,
            names=cat_col,
            values=val_col,
            title=f"{val_col} Distribution by {cat_col}",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8501, debug=False)

