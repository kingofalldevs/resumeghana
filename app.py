import os
import json
import base64
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader
from prompts import RESUME_GENERATION_PROMPT, RESUME_WIZARD_PROMPT, RESUME_ENHANCER_PROMPT

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure upload folder to handle images (avoids session cookie overflow)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_text_from_pdf(file):
    """
    Extracts text from an uploaded PDF file.
    """
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""


def parse_resume_text(text):
    """
    Uses OpenAI to parse unstructured resume text into structured JSON.
    """
    system_prompt = """
    You are a resume parser. Extract the following fields from the resume text:
    - name
    - role (target role or current job title)
    - skills (summary of skills)
    - experience (summary of work history)
    - education (summary of education)
    
    Return ONLY valid JSON with these exact keys:
    {"name": "", "role": "", "skills": "", "experience": "", "education": ""}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error parsing resume: {e}")
        return {}


def get_ai_resume_review(resume_data):
    """
    Sends resume data to OpenAI and retrieves a structured JSON review.
    """

    system_prompt = """
    You are an expert AI Career Coach and ATS Specialist.
    Review the resume and return ONLY valid JSON using this structure:

    {
      "score": 1-100,
      "summary": "Explanation of score",
      "strengths": [],
      "weaknesses": [],
      "missing_skills": [],
      "formatting_advice": "",
      "rewritten_bullets": [
        {"original": "", "improved": ""}
      ]
    }
    """

    user_content = f"""
    Name: {resume_data.get('name')}
    Target Role: {resume_data.get('role')}

    Skills:
    {resume_data.get('skills')}

    Experience:
    {resume_data.get('experience')}

    Education:
    {resume_data.get('education')}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.6,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content), None

    except Exception as e:
        print("OpenAI error:", e)
        return None, str(e)


def generate_tailored_resume(resume_data):
    """
    Generates a professionally formatted HTML resume based on the input data.
    """
    system_prompt = RESUME_GENERATION_PROMPT

    # Prepare data for AI
    ai_data = resume_data.copy()
    
    # Handle photo: check for filename, read file, convert to base64
    photo_filename = ai_data.pop('photo_filename', None)
    photo_base64 = None
    
    if photo_filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
        if os.path.exists(file_path):
            with open(file_path, "rb") as img_file:
                photo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            ai_data['include_photo_placeholder'] = True
    
    user_content = f"Rewrite this resume for the role of {resume_data.get('role')}:\n\n{json.dumps(ai_data)}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            temperature=0.7
        )
        content = response.choices[0].message.content
        
        # Inject the photo back into the HTML if it exists
        if photo_base64:
            content = content.replace("PHOTO_PLACEHOLDER", f"data:image/jpeg;base64,{photo_base64}")
            
        return content
    except Exception as e:
        return f"<p>Error generating resume: {e}</p>"

@app.route("/api/suggest", methods=["POST"])
def suggest():
    data = request.json
    step = int(data.get('step'))
    form_data = data.get('formData')
    
    # Use Wizard Prompt for Contact (1) and Education (3)
    if step in [1, 3]:
        system_prompt = RESUME_WIZARD_PROMPT
        user_content = f"Current Step: {step}\nUser Data: {json.dumps(form_data)}"
    
    # Use Enhancer Prompt for Experience (2) and Skills (4)
    else:
        system_prompt = RESUME_ENHANCER_PROMPT
        
        # Construct structured input for the enhancer
        resume_object = {
            "identity": {
                "name": form_data.get('name'),
                "target_title": form_data.get('role'),
                "job_level": form_data.get('job_level'),
                "job_location": form_data.get('location_target')
            },
            "summary_inputs": {
                "industry": form_data.get('job_type'),
                "years_experience": form_data.get('years_experience'),
                "career_objective": form_data.get('career_objective'),
                "abilities": form_data.get('abilities')
            },
            "experience": [{
                "role": form_data.get('role'),
                "bullet_intents": form_data.get('experience', '').split('\n'),
                "seniority": form_data.get('job_level')
            }],
            "skills": {"technical_or_professional": form_data.get('skills', '').split(',') if form_data.get('skills') else [], "soft": []},
            "optional_sections": {
                "certifications": form_data.get('certifications', '').split('\n') if form_data.get('certifications') else [],
                "relevant_coursework": form_data.get('relevant_coursework', '').split(',') if form_data.get('relevant_coursework') else [],
                "projects": [],
                "languages": [],
                "links": {}
            },
            "job_type": form_data.get('job_type')
        }
        user_content = json.dumps(resume_object)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        return jsonify(json.loads(response.choices[0].message.content))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/build", methods=["GET", "POST"])
def builder():
    if request.method == "POST":
        resume_data = {}

        # Check for file upload (expects <input type="file" name="resume_file"> in the form)
        if 'resume_file' in request.files:
            file = request.files['resume_file']
            if file.filename != '':
                text = extract_text_from_pdf(file)
                if text:
                    resume_data = parse_resume_text(text)

        # Fallback to form data if no file uploaded or parsing failed
        if not resume_data:
            resume_data = {
                "name": request.form.get("name"),
                "phone": request.form.get("phone"),
                "email": request.form.get("email"),
                "country": request.form.get("country"),
                "job_type": request.form.get("job_type"),
                "job_level": request.form.get("job_level"),
                "years_experience": request.form.get("years_experience"),
                "location_target": request.form.get("location_target"),
                "functional_focus": request.form.get("functional_focus"),
                "role": request.form.get("role"),
                "skills": request.form.get("skills"),
                "abilities": request.form.get("abilities"),
                "career_objective": request.form.get("career_objective"),
                "experience": request.form.get("experience"),
                "education": request.form.get("education"),
                "certifications": request.form.get("certifications"),
                "relevant_coursework": request.form.get("relevant_coursework"),
                "links": request.form.get("links")
            }

            # Handle Profile Photo Upload
            if 'profile_photo' in request.files:
                photo = request.files['profile_photo']
                if photo.filename != '':
                    try:
                        filename = secure_filename(photo.filename)
                        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        resume_data['photo_filename'] = filename
                    except Exception as e:
                        print(f"Error processing photo: {e}")

        if not resume_data.get("skills") or not resume_data.get("experience"):
            flash("Please provide at least Skills and Experience.", "error")
            return redirect(url_for("builder"))

        # Store data in session for the tailoring step
        session['resume_data'] = resume_data

        analysis, error = get_ai_resume_review(resume_data)

        if analysis:
            return render_template(
                "results.html",
                analysis=analysis,
                original=resume_data
            )
        else:
            flash(f"AI analysis failed: {error}", "error")
            return redirect(url_for("builder"))

    return render_template("builder.html")


@app.route("/tailor")
def tailor():
    resume_data = session.get('resume_data')
    if not resume_data:
        flash("Session expired. Please start over.", "error")
        return redirect(url_for("builder"))
    
    tailored_content = generate_tailored_resume(resume_data)
    return render_template("tailored.html", content=tailored_content)

if __name__ == "__main__":
    app.run(debug=True)
