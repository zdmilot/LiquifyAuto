# Import necessary libraries
import requests
from flask import Flask, render_template, session, request, redirect, url_for, Response
from flask_session import Session
import msal
import app_config
import pandas as pd
import openai
import os
import io
from docx import Document


app = Flask(__name__)
app.config.from_object(app_config)
Session(app)

# Initialize OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Route for the main page
@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get("user"):
        return redirect(url_for("login"))


    if request.method == 'POST':
         # Check if a file is uploaded
        if 'file' not in request.files:
            error_message = "No file uploaded. Please select a file and try again."
            return render_template('index.html', error=error_message)

        # Get input data
        input_file = request.files['file']
        if not input_file.filename:  # Check if the filename is empty (i.e., no file selected)
            error_message = "No file selected. Please select a file and try again."
            return render_template('index.html', user=session["user"], version=msal.__version__, error=error_message)
        file_extension = input_file.filename.split('.')[-1]
        output_format = request.form.get('output_format', 'table')

        # Process input data based on file type
        if file_extension == 'xlsx':
            df = pd.read_excel(input_file, engine='openpyxl')
            lines = [f"{row[df.columns[0]]}{row[df.columns[1]]}{row[df.columns[2]]}" for _, row in df.iterrows()]
        elif file_extension == 'txt':
            txt_data = io.StringIO(input_file.read().decode('utf-8'))
            lines = txt_data.readlines()
        elif file_extension == 'docx':
            doc = Document(input_file)
            lines = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
        else:
            return 'Unsupported file format', 400

        processed_data = process_data(lines)
        session['processed_data'] = processed_data  # Save the processed data in the session

        # Render output based on the chosen format
        if output_format == 'csv':
            return generate_csv(processed_data)
        elif output_format == 'table':
            return render_template('index.html',user=session["user"], version=msal.__version__, data=processed_data)
        elif 'download_csv' in request.form:  # Check if the download CSV button was clicked
            return generate_csv(session.get('processed_data', []))
        else:
            return render_template('index.html', user=session["user"], version=msal.__version__)
    return render_template('index.html', user=session["user"], version=msal.__version__)

# Function to process input data
def process_data(lines):
    processed_data = []

    for index, line in enumerate(lines):
        # Use the line as the raw data
        raw_data = line.strip()

        # Call the ChatGPT API to process the raw data
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Given the laboratory sample information: \"{raw_data}\", separate the sample type, liquid class, and volume with commas. do not include labels such as sample type or use any symbols other than commas in the response",
            max_tokens=50,
            n=1,
            stop=None,
            temperature=0.5,
        )

        # Extract the processed information
        result = response.choices[0].text.strip()

        try:
            # Split the result and assign to variables
            sample_type, liquid_class, volume = result.split(',')

            # Add the processed information to the list
            processed_data.append({
                'sample_type': sample_type,
                'liquid_class': liquid_class,
                'volume': volume
            })
        except ValueError:
            print(f"Error: Not enough values to unpack for row {index}. Raw data: {raw_data}. Result: {result}")

    return processed_data

# Function to generate CSV output
def generate_csv(data):
    csv_data = "Sample Type,Liquid Class,Volume\n"
    for row in data:
        csv_data += f"{row['sample_type']},{row['liquid_class']},{row['volume']}\n"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=output.csv"}
    )

# Function to disable caching
@app.after_request
def add_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

#Function to download CSV data using session ID
@app.route('/restart', methods=['POST'])
def restart():
    if 'download_csv' in request.form:
        return generate_csv(session.get('processed_data', []))
    session.pop('processed_data', None)
    return redirect(url_for('index'))

@app.route("/login")
def login():
    # Collect end user consent upfront
    session["flow"] = _build_auth_code_flow(scopes=app_config.SCOPE)
    return render_template("login.html", auth_url=session["flow"]["auth_uri"], version=msal.__version__)

@app.route(app_config.REDIRECT_PATH)  # Its absolute URL must match your app's redirect_uri set in AAD
def authorized():
    try:
        cache = _load_cache()
        result = _build_msal_app(cache=cache).acquire_token_by_auth_code_flow(
            session.get("flow", {}), request.args)
        if "error" in result:
            return render_template("auth_error.html", result=result)
        session["user"] = result.get("id_token_claims")
        _save_cache(cache)
    except ValueError:  # Usually caused by CSRF
        pass  # Simply ignore them
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()  # Wipe out user and its token cache from session
    return redirect(  # Also logout from your tenant's web session
        app_config.AUTHORITY + "/oauth2/v2.0/logout" +
        "?post_logout_redirect_uri=" + url_for("index", _external=True))

@app.route("/graphcall")
def graphcall():
    token = _get_token_from_cache(app_config.SCOPE)
    if not token:
        return redirect(url_for("login"))
    graph_data = requests.get(  # Use token to call downstream service
        app_config.ENDPOINT,
        headers={'Authorization': 'Bearer ' + token['access_token']},
        ).json()
    return render_template('display.html', result=graph_data)


def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

def _build_msal_app(cache=None, authority=None):
    return msal.ConfidentialClientApplication(
        app_config.CLIENT_ID, authority=authority or app_config.AUTHORITY,
        client_credential=app_config.CLIENT_SECRET, token_cache=cache)

def _build_auth_code_flow(authority=None, scopes=None):
    redirect_uri_value = url_for("authorized", _external=True)
    return _build_msal_app(authority=authority).initiate_auth_code_flow(
        scopes or [],
        redirect_uri=redirect_uri_value)

def _get_token_from_cache(scope=None):
    cache = _load_cache()  # This web app maintains one cache per session
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:  # So all account(s) belong to the current signed-in user
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(cache)
        return result

app.jinja_env.globals.update(_build_auth_code_flow=_build_auth_code_flow)  # Used in template


if __name__ == "__main__":
    app.run()

