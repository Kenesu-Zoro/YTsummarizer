from flask import Flask, request, jsonify, send_from_directory, render_template_string
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

# Initialize Flask
app = Flask(__name__, static_folder=".", static_url_path="")

# ----------------------------- Email Configuration -----------------------------
SMTP_SERVER = 'smtp.gmail.com'  # Gmail SMTP server
SMTP_PORT = 587  # Gmail SMTP port
EMAIL_ADDRESS = 'smartscribe69420@gmail.com'  # Your email address
EMAIL_PASSWORD = 'kgoq elrm roqr wfqv'  # Your app password
RECIPIENT_EMAIL = 'smartscribe69420@gmail.com'  # Email to receive form submissions

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

# ----------------------------- YouTube Summarizer Configuration -----------------------------
PROMPT = """
You are a professional educational video summarizer. Your task is to create a clean, visually structured, and highly readable summary of the provided transcript. Follow these formatting rules:

1. **Ignore any sponsorships, advertisements, or unrelated promotions.**

2. **Focus on the educational content** and key information in the transcript.

3. **Structure the summary as follows**:  
   - Use clear, bold headings for sections (e.g., Key Points, Conclusion, Historical Context).  
   - Use bullet points for important points.  
   - Add subpoints under main bullet points when more details are needed (use two spaces for indentation).  
   - Include numbered steps for processes or sequential information.  

4. **Enhance the summary for longer transcripts**:  
   - Add **extra details or explanations** where necessary to ensure clarity, especially when covering technical, historical, or step-by-step content.  
   - Include **examples, anecdotes, or key insights** mentioned in the video to make the summary richer and more engaging.  
   - Provide a **recap or conclusion** that ties together the main themes or takeaways.  

5. **Include Sentiment Analysis at the end**:  
   - Assess the tone and delivery of the video (e.g., positive, neutral, motivational, critical).  
   - Highlight how the speaker’s attitude influences the educational content or its delivery.  
   - Comment on whether the video leaves the viewer inspired, informed, or with a call to action.  

6. **Ensure readability**:  
   - Use concise sentences to avoid dense paragraphs.  
   - Add empty lines between bullet points for better readability.  
   - Bold text only for headings and key terms that need emphasis.

7. The summary should be under **300 words** for short videos. For longer videos, create a **detailed summary under 600 words**, including sentiment analysis.

Here is the transcript:  
"""


# ----------------------------- Helper Functions -----------------------------
def get_video_id(video_url):
    """
    Extract the video ID from a YouTube URL.
    """
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, video_url)
    if match:
        return match.group(1)
    return None

def get_thumbnail_url(video_url):
    video_id = get_video_id(video_url)
    if video_id:
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    return None

def extract_transcript_details(video_url):
    """
    Extract the YouTube video transcript as a single text string.
    Attempts both manual and auto-generated transcripts in any available language.
    """
    try:
        video_id = get_video_id(video_url)
        if not video_id:
            return {"error": "Invalid YouTube video URL."}

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Attempt to fetch manual English transcript
        try:
            transcript = transcript_list.find_transcript(['en'])
            transcript_data = transcript.fetch()
            return " ".join([entry["text"] for entry in transcript_data])
        except NoTranscriptFound:
            pass  # Continue if manual English transcript is not available

        # Attempt auto-generated English transcript
        try:
            transcript = transcript_list.find_generated_transcript(['en'])
            transcript_data = transcript.fetch()
            return " ".join([entry["text"] for entry in transcript_data])
        except NoTranscriptFound:
            pass  # Continue if auto-generated English transcript is not available

        # Fallback: Use any available language transcript
        for transcript in transcript_list:
            try:
                transcript_data = transcript.fetch()
                return " ".join([entry["text"] for entry in transcript_data])
            except Exception:
                continue

        return {"error": "No transcripts available in any language."}

    except TranscriptsDisabled:
        return {"error": "Transcripts are disabled for this video."}
    except Exception as e:
        return {"error": f"An error occurred while fetching the transcript: {str(e)}"}

def generate_gemini_content(transcript_text):
    try:
        trimmed_transcript = transcript_text[:2000]
        response = genai.GenerativeModel("gemini-pro").generate_content(PROMPT + trimmed_transcript)
        return response.text if response.text else "Summary unavailable."
    except Exception as e:
        return f"Error summarizing transcript: {str(e)}"

# ----------------------------- Routes -----------------------------

# Route to serve index.html
@app.route("/", methods=["GET"])
def home():
    return send_from_directory(".", "index.html")

# Route for email form submission
@app.route("/submit-form", methods=["POST"])
def submit_form():
    try:
        # Get form data from the request
        data = request.form
        name = data.get('name')
        email = data.get('email')
        message = data.get('message')
        
        # Construct the email message
        email_subject = "New Form Submission"
        email_body = f"You received a new form submission:\n\nName: {name}\nEmail: {email}\nMessage: {message}"

        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = email_subject
        msg.attach(MIMEText(email_body, 'plain'))

        # Send the email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        
        # Show a presentable submission success message
        return render_template_string(SUCCESS_PAGE)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# Route to transcribe and summarize YouTube videos
@app.route("/transcribe", methods=["POST"])
def transcribe():
    data = request.get_json()
    video_url = data.get("video_url")
    if not video_url:
        return jsonify({"error": "No YouTube video URL provided."}), 400

    # Get thumbnail URL
    thumbnail_url = get_thumbnail_url(video_url)
    if not thumbnail_url:
        return jsonify({"error": "Invalid YouTube URL format."}), 400

    # Fetch transcript
    transcript = extract_transcript_details(video_url)
    if isinstance(transcript, dict) and "error" in transcript:
        return jsonify({"error": transcript["error"]}), 400

    # Generate summary
    summary = generate_gemini_content(transcript)

    return jsonify({"thumbnail_url": thumbnail_url, "summary": summary})

# ----------------------------- Run Flask Server -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)