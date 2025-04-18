import gradio as gr
import json
import re
import os
import google.generativeai as genai
import fitz  # PyMuPDF
import tempfile
import shutil
import traceback

# Setup Gemini API 
# Note: Set your own API key here or use environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "your-api-key-here")
genai.configure(api_key=GOOGLE_API_KEY)

# Models
flash_model = genai.GenerativeModel('gemini-1.5-flash')
pro_model = genai.GenerativeModel('gemini-1.5-pro')  # For complex analysis

def extract_text_from_pdf(pdf_file):
    """Extract text from a PDF file."""
    temp_file = None
    try:
        # Handle different types of file inputs
        if isinstance(pdf_file, str):
            # If it's a path string
            file_path = pdf_file
        else:
            # If it's a file object from Gradio, save it to a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.close()
            
            # Copy file data to the temporary file
            with open(temp_file.name, 'wb') as f:
                if hasattr(pdf_file, 'read'):
                    # If it has a read method (file-like object)
                    shutil.copyfileobj(pdf_file, f)
                elif hasattr(pdf_file, 'name'):
                    # If it has a name attribute (like UploadFile)
                    with open(pdf_file.name, 'rb') as src:
                        shutil.copyfileobj(src, f)
                else:
                    # Try direct copy as bytes
                    f.write(pdf_file)
            
            file_path = temp_file.name
        
        # Open the PDF file
        doc = fitz.open(file_path)
        
        # Extract text from each page
        text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        
        return text.strip()
    except Exception as e:
        print(f"PDF extraction error: {str(e)}")
        traceback.print_exc()
        return f"Error extracting text from PDF: {str(e)}"
    finally:
        # Ensure document is closed before file is deleted
        if 'doc' in locals():
            doc.close()

        # Clean up temporary file if created
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                print(f"Could not delete temp file: {temp_file.name}. Error: {e}")

def analyze_resume(resume_text):
    """Extract key information from a resume using Gemini."""
    prompt = f"""
    Analyze the following resume and extract key information in a structured JSON format.
    Include the following fields:
    1. name: The candidate's full name
    2. contact_info: Email and phone number if present
    3. summary: A brief professional summary
    4. skills: List of technical and soft skills
    5. experience: List of work experiences with company, title, dates, and achievements
    6. education: Academic background
    7. projects: Any mentioned projects with descriptions
    8. strengths: The candidate's 3-5 main professional strengths based on the resume
    
    Resume:
    {resume_text}
    
    Return only the JSON without any explanations or markdown formatting.
    """
    
    response = pro_model.generate_content(prompt)
    
    # Extract JSON from response
    try:
        json_str = response.text
        # Remove markdown code block formatting if present
        json_str = re.sub(r'```json|```', '', json_str).strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}")
        print(f"Raw response: {response.text}")
        return {"error": "Failed to parse resume data"}

def analyze_job_description(job_description):
    """Extract key information from a job description using Gemini."""
    prompt = f"""
    Analyze the following job description and extract key information in a structured JSON format.
    Include the following fields:
    1. company_name: The company posting the job (if mentioned)
    2. job_title: The position title
    3. location: Job location (remote, hybrid, or physical location) if mentioned
    4. job_summary: A brief summary of the role
    5. required_skills: List of required technical and soft skills
    6. preferred_skills: List of preferred or nice-to-have skills
    7. responsibilities: Key job responsibilities
    8. qualifications: Required education and experience
    9. keywords: 5-10 important keywords from the job description
    
    Job Description:
    {job_description}
    
    Return only the JSON without any explanations or markdown formatting.
    """
    
    response = pro_model.generate_content(prompt)
    
    # Extract JSON from response
    try:
        json_str = response.text
        # Remove markdown code block formatting if present
        json_str = re.sub(r'```json|```', '', json_str).strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}")
        print(f"Raw response: {response.text}")
        return {"error": "Failed to parse job description data"}

def match_skills(resume_data, job_data):
    """Match resume skills against job requirements and identify gaps."""
    prompt = f"""
    Compare the candidate's skills and qualifications with the job requirements and provide an analysis in JSON format.
    
    Resume Data:
    {json.dumps(resume_data, indent=2)}
    
    Job Data:
    {json.dumps(job_data, indent=2)}
    
    Generate a JSON response with the following fields:
    1. matching_skills: List of skills the candidate has that match the job requirements
    2. missing_skills: List of required skills the candidate appears to be missing
    3. relevant_experience: List of candidate experiences relevant to this job
    4. overall_match_percentage: Estimated percentage match between the candidate and job (0-100)
    5. strengths_to_highlight: Key strengths from the resume that should be emphasized in the application
    6. suggested_talking_points: Specific resume elements to mention in the application email
    
    Return only the JSON without any explanations or markdown formatting.
    """
    
    response = pro_model.generate_content(prompt)
    
    # Extract JSON from response
    try:
        json_str = response.text
        # Remove markdown code block formatting if present
        json_str = re.sub(r'```json|```', '', json_str).strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}")
        print(f"Raw response: {response.text}")
        return {"error": "Failed to match skills"}

def generate_email_advanced(resume_data, job_data, skills_match, recipient_name="Hiring Manager", email_tone="professional", additional_info=""):
    """Generate a tailored job application email using detailed analysis."""
    # Define email tones
    tone_descriptions = {
        "professional": "formal and polished",
        "enthusiastic": "energetic and passionate",
        "concise": "brief but comprehensive",
        "conversational": "friendly and approachable"
    }
    
    tone_desc = tone_descriptions.get(email_tone, "professional and well-structured")
    
    prompt = f"""
    Generate a {tone_desc} job application email for the following scenario:
    
    Resume Information:
    {json.dumps(resume_data, indent=2)}
    
    Job Information:
    {json.dumps(job_data, indent=2)}
    
    Skills Match Analysis:
    {json.dumps(skills_match, indent=2)}
    
    Recipient: {recipient_name}
    Additional Information to Include: {additional_info}
    
    The email should:
    1. Have an attention-grabbing subject line
    2. Start with a professional greeting
    3. Include a strong opening paragraph explaining interest in the position
    4. Highlight 3-4 of the candidate's most relevant skills and experiences for this specific job
    5. Address any potential skill gaps with transferable skills or eagerness to learn
    6. Include a brief paragraph on why the candidate is interested in this specific company
    7. End with a clear call to action and professional closing
    8. Be concise (no more than 300-400 words total)
    
    Format the response with "Subject:" at the top followed by the email body.
    """
    
    response = pro_model.generate_content(prompt)
    return response.text

def generate_basic_email(resume_text, job_description, user_name, company_name, job_role):
    """Generate a basic email using direct approach."""
    prompt = f"""
    You are a professional mail writer.

    Write a personalized email that {user_name} can send to a hiring manager at {company_name} for the role of {job_role}.
    Use the resume content and job description below to tailor the email. The tone should be professional, polite, and confident.

    --- RESUME ---
    {resume_text}

    --- JOB DESCRIPTION ---
    {job_description}

    --- EMAIL FORMAT ---
    Subject: Application for {job_role} at {company_name}

    [Write the full email body here]
    """

    response = flash_model.generate_content(prompt)
    return response.text

def process_application(resume_file, job_desc, user_name, company_name, job_title, recipient_name, email_tone, additional_info, use_advanced=True):
    """Process application and generate email."""
    try:
        # Check for required inputs
        if resume_file is None:
            return "Error: Please upload a resume file", "", "", ""
        
        if not job_desc:
            return "Error: Please provide a job description", "", "", ""
        
        if not user_name:
            user_name = "Job Applicant"
            
        if not company_name:
            company_name = "the Company"
            
        if not job_title:
            job_title = "the Position"
        
        # Extract text from resume
        resume_text = extract_text_from_pdf(resume_file)
        
        # Check if text extraction was successful
        if resume_text.startswith("Error"):
            return f"{resume_text}. Please ensure it's a valid PDF file.", "", "", ""
            
        if use_advanced:
            # Advanced approach (analyze resume and job, match skills, generate email)
            print("Analyzing resume...")
            resume_data = analyze_resume(resume_text)
            
            print("Analyzing job description...")
            job_data = analyze_job_description(job_desc)
            
            print("Matching skills...")
            skills_match = match_skills(resume_data, job_data)
            
            print("Generating email...")
            email = generate_email_advanced(resume_data, job_data, skills_match, recipient_name, email_tone, additional_info)
            
            # Prepare summary information
            resume_summary = f"**Name:** {resume_data.get('name', 'Not found')}\n\n"
            resume_summary += f"**Skills:** {', '.join(resume_data.get('skills', ['Not found']))}\n\n"
            experience_count = len(resume_data.get('experience', []))
            resume_summary += f"**Experience:** {experience_count} position{'s' if experience_count != 1 else ''}\n\n"
            
            job_summary = f"**Position:** {job_data.get('job_title', job_title)}\n\n"
            if 'company_name' in job_data:
                job_summary += f"**Company:** {job_data.get('company_name', company_name)}\n\n"
            job_summary += f"**Required Skills:** {', '.join(job_data.get('required_skills', ['Not found']))}\n\n"
            
            match_summary = f"**Match Percentage:** {skills_match.get('overall_match_percentage', 'N/A')}%\n\n"
            match_summary += f"**Matching Skills:** {', '.join(skills_match.get('matching_skills', ['None']))}\n\n"
            match_summary += f"**Missing Skills:** {', '.join(skills_match.get('missing_skills', ['None']))}\n\n"
        else:
            # Basic approach (directly generate email)
            print("Using basic email generation...")
            email = generate_basic_email(resume_text, job_desc, user_name, company_name, job_title)
            resume_summary = "Basic mode: Resume analysis not performed"
            job_summary = "Basic mode: Job analysis not performed"
            match_summary = "Basic mode: Skills matching not performed"
        
        return resume_summary, job_summary, match_summary, email
    
    except Exception as e:
        # Print detailed error for debugging
        traceback.print_exc()
        return f"Error: {str(e)}", "", "", ""

# Create Gradio interface
with gr.Blocks(title="Smart Job Application Email Generator") as app:
    gr.Markdown("# Smart Job Application Email Generator")
    gr.Markdown("Upload your resume and provide a job description to generate a tailored application email")
    
    # Add error message component
    error_box = gr.Textbox(label="Status", visible=False)
    
    with gr.Row():
        with gr.Column():
            resume_file = gr.File(
                label="Upload Resume (PDF)",
                file_types=["pdf", ".pdf", "application/pdf"],
                file_count="single",
                type="binary"
            )
            job_desc = gr.Textbox(
                label="Job Description", 
                lines=8, 
                placeholder="Paste the full job description here..."
            )
            
            with gr.Row():
                user_name = gr.Textbox(label="Your Name", placeholder="John Doe")
                company_name = gr.Textbox(label="Company Name", placeholder="TechNova Inc.")
            
            with gr.Row():
                job_title = gr.Textbox(label="Job Title", placeholder="Full Stack Developer")
                recipient = gr.Textbox(label="Recipient Name", placeholder="Hiring Manager", value="Hiring Manager")
            
            tone = gr.Radio(
                label="Email Tone", 
                choices=["professional", "enthusiastic", "concise", "conversational"], 
                value="professional"
            )
            additional = gr.Textbox(
                label="Additional Information", 
                lines=3, 
                placeholder="Any specific points you want to mention..."
            )
            
            with gr.Row():
                use_advanced = gr.Checkbox(label="Use Advanced Analysis", value=True)
                submit_btn = gr.Button("Generate Email", variant="primary")
            
        with gr.Column():
            resume_summary = gr.Markdown(label="Resume Summary")
            job_summary = gr.Markdown(label="Job Summary")
            match_summary = gr.Markdown(label="Skills Match")
            email_output = gr.Textbox(label="Generated Email", lines=16)
    
    # Add helpful tips
    gr.Markdown("""
    ## Tips for Best Results
    - Make sure your resume is in PDF format
    - Include all relevant skills and experience in your resume
    - Provide as much detail as possible in the job description
    - For advanced mode, the analysis may take 30-60 seconds to complete
    """)
    
    def on_submit(resume_file, job_desc, user_name, company_name, job_title, recipient_name, email_tone, additional_info, use_advanced):
        # Pre-submission validation
        if resume_file is None:
            return "Error: No resume uploaded", "", "", "", gr.update(value="Please upload a resume file", visible=True)
        
        # Process the application
        resume_summary, job_summary, match_summary, email = process_application(
            resume_file, job_desc, user_name, company_name, job_title, 
            recipient_name, email_tone, additional_info, use_advanced
        )
        
        if resume_summary.startswith("Error"):
            return resume_summary, job_summary, match_summary, email, gr.update(value=resume_summary, visible=True)
        else:
            return resume_summary, job_summary, match_summary, email, gr.update(value="Success! Email generated.", visible=True)
    
    submit_btn.click(
        on_submit,
        inputs=[resume_file, job_desc, user_name, company_name, job_title, recipient, tone, additional, use_advanced],
        outputs=[resume_summary, job_summary, match_summary, email_output, error_box]
    )
    
    # Clear the form when a new file is uploaded
    def on_file_upload(file):
        if file is not None:
            return gr.update(value="Resume uploaded successfully. Click 'Generate Email' when ready.", visible=True)
        return gr.update(visible=False)
    
    resume_file.upload(
        on_file_upload,
        inputs=[resume_file],
        outputs=[error_box]
    )

# Launch the app when running this script directly
if __name__ == "__main__":
    print("Starting the Smart Job Application Email Generator...")
    print("Visit the URL below to access the web interface:")
    print("Note: Make sure to upload a PDF resume file")
    app.launch() 