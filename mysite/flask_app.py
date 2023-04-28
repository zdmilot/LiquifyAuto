# Import necessary libraries
from flask import Flask, render_template, request, Response, redirect, session, url_for
import pandas as pd
import openai
import os
import io
from docx import Document


# Initialize Flask app and OpenAI API key
app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
app.secret_key = os.urandom(24)  # Add a secret key for the session

# Route for the main page
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
         # Check if a file is uploaded
        if 'file' not in request.files:
            error_message = "No file uploaded. Please select a file and try again."
            return render_template('index.html', error=error_message)

        # Get input data
        input_file = request.files['file']
        if not input_file.filename:  # Check if the filename is empty (i.e., no file selected)
            error_message = "No file selected. Please select a file and try again."
            return render_template('index.html', error=error_message)
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
            return render_template('index.html', data=processed_data)
        elif 'download_csv' in request.form:  # Check if the download CSV button was clicked
            return generate_csv(session.get('processed_data', []))
        else:
            return render_template('index.html')
    return render_template('index.html')

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

#Enables debugging module NOT FOR PRODUCTION ENVIRONMENT
if __name__ == '__main__':
    app.run(debug=True)