import uuid
import msal
from flask import Flask, render_template, request, Response, redirect, session, url_for, url_for
import pandas as pd
import openai
import os


app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
app.secret_key = os.urandom(24)  # Add a secret key for the session

# Add the following variables with the information obtained from the Azure portal
CLIENT_ID = os.getenv("APP_CLIENT_ID")
CLIENT_SECRET = os.getenv("APP_CLIENT_SECRET")
TENANT_ID = os.getenv("APP_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0/me"

# MSAL app instance
msal_app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
)

@app.route("/login")
def login():
    session["state"] = str(uuid.uuid4())
    auth_url = msal_app.get_authorization_request_url(
        ["User.Read"],
        state=session["state"],
        redirect_uri=url_for("auth_redirect", _external=True),
    )
    return redirect(auth_url)


@app.route("/auth/redirect")
def auth_redirect():
    if request.args.get("state") != session.get("state"):
        return "State mismatch", 400
    if "error" in request.args:
        return f"Error: {request.args['error']} {request.args['error_description']}"

    token_response = msal_app.acquire_token_by_authorization_code(
        request.args["code"],
        scopes=["User.Read"],
        redirect_uri=url_for("auth_redirect", _external=True),
    )

    if "error" in token_response:
        return f"Error in token response: {token_response['error']} {token_response['error_description']}"

    session["token_cache"] = token_response

    user_info = msal_app.acquire_token_for_client(["User.Read"])
    session["user"] = user_info

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get("user"):
        return redirect(url_for("login"))

    if request.method == 'POST':
        excel_file = request.files['file']
        output_format = request.form.get('output_format', 'table')
        df = pd.read_excel(excel_file, engine='openpyxl')
        processed_data = process_data(df)

        if output_format == 'csv':
            return generate_csv(processed_data)
        else:
            return render_template('index.html', data=processed_data)
    return render_template('index.html')

def process_data(df):
    processed_data = []

    for index, row in df.iterrows():
        # Concatenate the first three columns of data regardless of name
        raw_data = f"{row[df.columns[0]]}{row[df.columns[1]]}{row[df.columns[2]]}"

        # Call the ChatGPT API to process the raw data
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Given the laboratory sample information: \"{raw_data}\", please separate the sample type, liquid class, and volume with commas. do not include labels such as sample type or use any symbols other than commas in the response",
            max_tokens=50,
            n=1,
            stop=None,
            temperature=0.5,
        )

        # Extract the processed information
        result = response.choices[0].text.strip()

        try:
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




def generate_csv(data):
    csv_data = "Sample Type,Liquid Class,Volume\n"
    for row in data:
        csv_data += f"{row['sample_type']},{row['liquid_class']},{row['volume']}\n"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=output.csv"}
    )


@app.after_request
def add_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/restart', methods=['POST'])
def restart():
    session.pop('processed_data', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)

