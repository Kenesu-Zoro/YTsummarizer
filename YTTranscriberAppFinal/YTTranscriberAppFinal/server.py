from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Load environment variables
load_dotenv()

# Configure Google Generative AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__, static_folder=".", static_url_path="")

PROMPT = """
You are an expert educational video summarizer. Your task is to create a clean, structured, and visually clear summary. Follow these rules:
1. Ignore any sponsorships, advertisements, or unrelated promotions.
2. Focus on the educational content and key information in the video.
3. Highlight key concepts and explanations clearly in short paragraphs or bullet points.
4. Avoid reproducing any copyrighted text verbatim. Summarize using your own words.
5. The summary should be clear, concise, and always provided in English.
6. **Include Sentiment Analysis at the end**:  
   - Assess the tone and delivery of the video (e.g., positive, neutral, motivational, critical).  
   - Highlight how the speaker’s attitude influences the educational content or its delivery.  
   - Comment on whether the video leaves the viewer inspired, informed, or with a call to action. 
   - No sentiment Analysis for non Educational videos 

Here is the transcript:
"""

# ----------------------------- Email Configuration -----------------------------
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = 'smartscribe69420@gmail.com'
EMAIL_PASSWORD = 'kgoq elrm roqr wfqv'
RECIPIENT_EMAIL = 'smartscribe69420@gmail.com'

# Success Page Template
SUCCESS_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Submission Successful</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; color: #333; }
        h1 { color: #4CAF50; }
        p { font-size: 18px; }
        .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); display: inline-block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Form Submitted Successfully!</h1>
        <p>Thank you for reaching out. We will get back to you shortly.</p>
    </div>
</body>
</html>
'''

# Failure Page Template
FAILURE_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Submission Failed</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; color: #333; }
        h1 { color: #E53935; }
        p { font-size: 18px; }
        .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); display: inline-block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Form Submission Failed!</h1>
        <p>We encountered an error while processing your request. Please try again later.</p>
    </div>
</body>
</html>
'''

# ----------------------------- YouTube Transcription Helpers -----------------------------
def get_video_id(url):
    regex = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_thumbnail_url(video_url):
    video_id = get_video_id(video_url)
    if not video_id:
        raise ValueError("Invalid YouTube video URL.")
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

def extract_transcript_details(video_url):
    try:
        video_id = get_video_id(video_url)
        if not video_id:
            return {"error": "Invalid YouTube video URL."}
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_transcript(['en'])
            transcript_data = transcript.fetch()
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
                transcript_data = transcript.fetch()
            except NoTranscriptFound:
                try:
                    transcript = next(iter(transcript_list))
                    transcript_data = transcript.fetch()
                except Exception:
                    return {"error": "No transcripts available in any language."}

        return " ".join([entry.text for entry in transcript_data])

    except TranscriptsDisabled:
        return {"error": "Transcripts are disabled for this video."}
    except Exception as e:
        return {"error": f"Failed to fetch transcript: {str(e)}"}

def generate_gemini_content(transcript_text):
    try:
        trimmed_transcript = transcript_text[:2000]
        response = genai.GenerativeModel("models/gemini-1.5-flash").generate_content(PROMPT + trimmed_transcript)
        return response.text if response.text else "Summary unavailable."
    except Exception as e:
        if "429" in str(e):
            return "Rate limit exceeded. Please wait a few minutes and try again."
        return f"Error summarizing transcript: {str(e)}"

# ----------------------------- Routes -----------------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def serve_page(path):
    return send_from_directory(".", path)

@app.route("/transcribe", methods=["POST"])
def transcribe():
    data = request.get_json()
    video_url = data.get("video_url")
    if not video_url:
        return jsonify({"error": "No YouTube video URL provided."}), 400

    try:
        thumbnail_url = get_thumbnail_url(video_url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    transcript_result = extract_transcript_details(video_url)
    if isinstance(transcript_result, dict) and "error" in transcript_result:
        return jsonify({"error": transcript_result["error"]}), 500

    summary = generate_gemini_content(transcript_result)

    return jsonify({
        "thumbnail_url": thumbnail_url,
        "summary": summary
    })

# ----------------------------- Contact Form Email Route -----------------------------
@app.route("/submit-form", methods=["POST"])
def submit_form():
    try:
        data = request.form
        name = data.get('name')
        email = data.get('email')
        message = data.get('message')

        email_subject = "New Form Submission"
        email_body = f"Name: {name}\nEmail: {email}\nMessage: {message}"

        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = email_subject
        msg.attach(MIMEText(email_body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
        server.quit()

        return SUCCESS_PAGE
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        return FAILURE_PAGE

# Diagnostic route to list available models
@app.route("/models", methods=["GET"])
def list_models():
    try:
        models = genai.list_models()
        return jsonify([model.name for model in models])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
