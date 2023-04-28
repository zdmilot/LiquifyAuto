# Lab Sample Data Processing Web App

This repository contains a Flask web application that allows users to upload an Excel file containing laboratory sample data, processes the data using OpenAI's ChatGPT API, and displays the processed data in a table or CSV format.

## Features

- Upload Excel files with laboratory sample data in the first three columns
- Process the data using OpenAI's ChatGPT API
- Display the processed data in a table format on the web app
- Download the processed data as a CSV file

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.6 or higher
- Pip (Python package manager)

### Installation

1. Clone the repository

git clone https://github.com/zdmilot/LiquifyAuto

2. Install required packages

pip install -r requirements.txt

3. Set up your OpenAI API key

Create a `.env` file in the project folder and add your OpenAI API key without quotes:

OPENAI_API_KEY=your_api_key_here


### Running the Application

1. Run the Flask application

python app.py


2. Access the web app at `http://localhost:5000`

## Usage

1. On the main page, click "Choose File" to select an Excel file containing laboratory sample data
2. Choose the output format (table or CSV) and click "Process Data"
3. The processed data will be displayed on the web app. You can also download the processed data as a CSV file by clicking "Download CSV"
