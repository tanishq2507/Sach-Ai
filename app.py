import re
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import json
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Configure your Perplexity API key
PERPLEXITY_API_KEY = "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"

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
        return transcript
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
        
        # Get text content
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

def analyze_content_with_perplexity(text, content_type, max_length=300):
    """Generate summary and critical analysis using Perplexity AI API"""
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
        # Generate a summary
        summary_prompt = f"""
        Please provide a concise summary of the following {"YouTube video transcript" if content_type == "youtube" else "article"}.
        
        CONTENT: {text[:4000]}
        """
        summary_payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a content summarizer."},
                {"role": "user", "content": summary_prompt}
            ]
        }
        summary_response = requests.post(api_url, headers=headers, json=summary_payload)
        if summary_response.status_code != 200:
            return {
                "summary": f"Error: API returned status code {summary_response.status_code}",
                "analysis": "Could not complete analysis due to API error"
            }
        summary_data = summary_response.json()
        summary = summary_data["choices"][0]["message"]["content"]
        
        # Generate critical analysis
        analysis_prompt = f"""
        Analyze the following {"YouTube video transcript" if content_type == "youtube" else "article"} for false statements, bias, and propaganda.
        
        CONTENT: {text[:4000]}
        """
        analysis_payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a fact-checker and media critic."},
                {"role": "user", "content": analysis_prompt}
            ]
        }
        analysis_response = requests.post(api_url, headers=headers, json=analysis_payload)
        if analysis_response.status_code != 200:
            return {
                "summary": summary,
                "analysis": f"Error: API returned status code {analysis_response.status_code}"
            }
        analysis_data = analysis_response.json()
        analysis = analysis_data["choices"][0]["message"]["content"]
        
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
        content = get_youtube_transcript(video_id)
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
    analysis_results = analyze_content_with_perplexity(content, content_type)
    return jsonify({
        'content_type': content_type,
        'metadata': metadata,
        'summary': analysis_results["summary"],
        'critical_analysis': analysis_results["analysis"],
        'source_url': url
    })

if __name__ == '__main__':
    app.run(debug=True)
