import re
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi, _errors
from flask import Flask, request, jsonify, render_template
import time
import os
from dotenv import load_dotenv

load_dotenv() 
app = Flask(__name__)

# Configure your Perplexity API key
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

def extract_youtube_id(url):
    """Extract YouTube video ID from URL"""
    youtube_regex = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None

def get_youtube_transcript(video_id):
    """Get transcript from YouTube video"""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = ' '.join([item['text'] for item in transcript_list])
        # Debug print for transcript text
        print("DEBUG: YouTube Transcript:", transcript)
        return transcript
    except _errors.TranscriptsDisabled:
        return "TRANSCRIPT_DISABLED"
    except _errors.NoTranscriptAvailable:
        return "NO_TRANSCRIPT"
    except Exception as e:
        return f"Error retrieving transcript: {str(e)}"

def extract_article_content(url):
    """Extract article content from news/blog sites"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text()
        
        # Extract source/publication
        source = ""
        meta_site_name = soup.find('meta', property='og:site_name')
        if meta_site_name and meta_site_name.get('content'):
            source = meta_site_name.get('content')
        
        # Extract publication date
        date = ""
        meta_date = soup.find('meta', property='article:published_time')
        if meta_date and meta_date.get('content'):
            date = meta_date.get('content')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        
        # Get text content from paragraphs
        paragraphs = soup.find_all('p')
        text = ' '.join([para.get_text() for para in paragraphs])
        
        return {
            "title": title,
            "source": source,
            "date": date,
            "content": text
        }
    except Exception as e:
        return {"error": f"Error extracting article: {str(e)}"}

def append_citations(text, citations):
    """Append citations to the text in markdown format if available."""
    if citations and isinstance(citations, list) and len(citations) > 0:
        citation_md = "\n\n### Citations\n"
        for idx, link in enumerate(citations, 1):
            citation_md += f"* [{idx}]({link})\n"
        return text + citation_md
    return text

def analyze_content_with_perplexity(text, content_type):
    """Generate summary and critical analysis using Perplexity AI API.
       The API returns the analysis as plain text or HTML, which we then pass directly to the frontend.
    """
    if not text or len(text) < 100:
        return {
            "summary": "Not enough content to analyze.",
            "analysis": "Content too short for meaningful analysis."
        }
    try:
        api_url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Generate summary with rich formatting instructions
        summary_prompt = f"""
        Please provide a comprehensive, well-structured summary of the following {"YouTube video transcript" if content_type == "youtube" else "article"}.
        
        Format your response with:
        1. Start with a concise overview paragraph
        2. Use ### headings to separate key sections when appropriate
        3. Include bullet points (using * or -) for key findings or main points
        4. Use **bold** for important points or terms
        5. If citing specific claims or statistics, reference them as [1], [2], etc.
        6. If applicable, include a "Key Takeaways" section at the end
        7. When mentioning sources or references, use proper markdown links: [text](URL)
        
        CONTENT: {text[:4000]}
        """
        
        summary_payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a content summarizer who provides well-structured, visually appealing summaries with clear organization, headings, and formatting."},
                {"role": "user", "content": summary_prompt}
            ]
        }
        
        # Add retry mechanism for API calls
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                summary_response = requests.post(api_url, headers=headers, json=summary_payload)
                summary_response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {
                        "summary": f"Error: API request failed after multiple attempts: {str(e)}",
                        "analysis": "Could not complete analysis due to API error"
                    }
        
        summary_data = summary_response.json()
        # Debug print for summary response
        print("DEBUG: Perplexity Summary Response:", summary_data)
        summary = summary_data["choices"][0]["message"]["content"]
        # Append citations if available
        summary = append_citations(summary, summary_data.get("citations", []))
        
        # Generate critical analysis with improved formatting instructions
        analysis_prompt = f"""
        Analyze the following {"YouTube video transcript" if content_type == "youtube" else "article"} for false statements, bias, and propaganda.
        
        Format your response with:
        1. Begin with an overview of the content's credibility and potential bias
        2. Use ### headings to separate key sections of your analysis
        3. For each questionable claim, format as:
           **Claim:** [the claim]
           **Verdict:** [True/False/Misleading/Partially True/etc.]
           [explanation with evidence]
        4. When citing sources, use proper markdown links: [text](URL)
        5. Use **bold** for important points or terms
        6. Use bullet points (using * or -) for listing related issues or patterns
        7. End with a conclusion section that summarizes your overall assessment
        
        CONTENT: {text[:4000]}
        """
        
        analysis_payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a fact-checker and media critic who provides thorough, well-structured analysis with proper formatting, clear verdicts, and evidence-based assessments."},
                {"role": "user", "content": analysis_prompt}
            ]
        }
        
        for attempt in range(max_retries):
            try:
                analysis_response = requests.post(api_url, headers=headers, json=analysis_payload)
                analysis_response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {
                        "summary": summary,
                        "analysis": f"Error: API request failed after multiple attempts: {str(e)}"
                    }
                    
        analysis_data = analysis_response.json()
        # Debug print for analysis response
        print("DEBUG: Perplexity Analysis Response:", analysis_data)
        analysis = analysis_data["choices"][0]["message"]["content"]
        # Append citations if available
        analysis = append_citations(analysis, analysis_data.get("citations", []))
        
        # Return both summary and analysis
        return {
            "summary": summary,
            "analysis": analysis
        }
    except Exception as e:
        import traceback
        print(f"Exception in analyze_content_with_perplexity: {str(e)}")
        print(traceback.format_exc())
        return {
            "summary": f"Error generating summary: {str(e)}",
            "analysis": f"Error performing analysis: {str(e)}"
        }

def determine_content_type(url):
    """Determine type of content from URL"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    else:
        return 'article'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    content_type = determine_content_type(url)
    metadata = {}
    
    if content_type == 'youtube':
        video_id = extract_youtube_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
            
        # Fetch video metadata first
        try:
            video_info_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            video_info_response = requests.get(video_info_url)
            video_info = video_info_response.json()
            metadata = {
                "title": video_info.get("title", "Unknown Title"),
                "author": video_info.get("author_name", "Unknown Creator"),
                "upload_date": "Not available"
            }
        except:
            metadata = {
                "title": "Unable to retrieve video details",
                "author": "Unknown",
                "upload_date": "Unknown"
            }
            
        # Get transcript and check if it's available
        content = get_youtube_transcript(video_id)
        # Print transcript for debugging
        print("DEBUG: Transcript content:", content)
        if content == "TRANSCRIPT_DISABLED" or content == "NO_TRANSCRIPT":
            return jsonify({
                'error': 'The transcript for this YouTube video is not available. Unable to analyze content.'
            }), 400
            
    else:
        article_data = extract_article_content(url)
        if isinstance(article_data, dict) and "error" not in article_data:
            content = article_data.get("content", "")
            metadata = {
                "title": article_data.get("title", "Unknown Title"),
                "source": article_data.get("source", "Unknown Source"),
                "publication_date": article_data.get("date", "Unknown Date")
            }
        else:
            return jsonify({'error': 'Failed to extract article content'}), 400

    # Only proceed with analysis if we have content to analyze
    analysis_results = analyze_content_with_perplexity(content, content_type)
    
    # Print Perplexity responses for debugging
    print("DEBUG: Perplexity Analysis Results:", analysis_results)
    
    # Return raw markdown/text to let the frontend handle formatting
    return jsonify({
        'content_type': content_type,
        'metadata': metadata,
        'summary': analysis_results["summary"],
        'critical_analysis': analysis_results["analysis"],
        'source_url': url
    })

if __name__ == '__main__':
    app.run(debug=True)
