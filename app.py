from flask import Flask, render_template, jsonify, request
import json
from datetime import datetime
import configparser
from arxiv_scraper import Paper
import os
import markdown
from qa_processor import QaProcessor
from markdown_processor import MarkdownProcessor
import glob

app = Flask(__name__)
qa_processor = QaProcessor()
md_processor = MarkdownProcessor()

def get_cached_dates():
    """Get list of available cached dates"""
    cache_files = glob.glob('out/cache/*_output.json')
    dates = []
    for file in cache_files:
        # Extract date from filename (format: YYYY-MM-DD_output.json)
        date_str = os.path.basename(file).replace('_output.json', '')
        try:
            # Verify it's a valid date
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            dates.append({
                'date': date_str,
                'display_date': date_obj.strftime('%B %d, %Y')
            })
        except ValueError:
            continue
    
    # Sort dates in reverse chronological order
    dates.sort(key=lambda x: x['date'], reverse=True)
    return dates

def cache_daily_output():
    """Cache current day's output"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Cache JSON output
    if os.path.exists('out/output.json'):
        os.makedirs('out/cache', exist_ok=True)
        cache_path = f'out/cache/{today}_output.json'
        if not os.path.exists(cache_path):
            with open('out/output.json', 'r') as src, open(cache_path, 'w') as dst:
                dst.write(src.read())

@app.route('/')
def index():
    """Main route to display papers"""
    try:
        # Cache daily output
        cache_daily_output()
        
        # Get requested date or use latest
        date_param = request.args.get('date')
        
        # Get list of available dates
        available_dates = get_cached_dates()
        
        # Determine which file to load
        if date_param and os.path.exists(f'out/cache/{date_param}_output.json'):
            json_file = f'out/cache/{date_param}_output.json'
            display_date = datetime.strptime(date_param, '%Y-%m-%d').strftime('%B %d, %Y')
        else:
            json_file = 'out/output.json'
            display_date = datetime.now().strftime('%B %d, %Y')
        
        # Load papers from JSON
        with open(json_file, 'r') as f:
            papers_dict = json.load(f)
        
        # Load header content
        with open('configs/header.md', 'r') as f:
            header_content = f.read()
        
        # Load paper topics/criteria
        with open('configs/paper_topics.txt', 'r') as f:
            topics_content = f.read()
        
        # Convert markdown to HTML
        header_html = md_processor.process_content(header_content)
        topics_html = md_processor.process_content(topics_content)
        
        # Convert the data structure to match Paper class
        papers = []
        for p in papers_dict.values():
            paper_data = {
                'arxiv_id': p.get('ARXIVID') or p.get('arxiv_id'),
                'title': p['title'],
                'abstract': p['abstract'],
                'authors': p['authors'],
                'url': f"https://arxiv.org/abs/{p.get('ARXIVID') or p.get('arxiv_id')}",
                'comment': p.get('COMMENT') or p.get('comment'),
                'relevance': p.get('RELEVANCE') or p.get('relevance'),
                'novelty': p.get('NOVELTY') or p.get('novelty')
            }
            papers.append(Paper(**paper_data))
        
        # Render template with all content
        return render_template('paper_template.html', 
                             papers=papers, 
                             date=display_date,
                             header_content=header_html,
                             topics_content=topics_html,
                             available_dates=available_dates,
                             current_date=date_param or datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        print(f"Error in index route: {e}")
        return f"Error loading papers: {str(e)}", 500

@app.route('/qa_progress/<arxiv_id>')
def get_qa_progress(arxiv_id):
    """Get the current progress of Q&A generation for a paper"""
    return jsonify(qa_processor.get_progress(arxiv_id))

@app.route('/get_qa/<arxiv_id>')
def get_qa(arxiv_id):
    try:
        # Load the paper data
        with open('out/output.json', 'r') as f:
            papers = json.load(f)
        
        # Find the paper with matching arxiv_id
        paper = None
        for p in papers.values():
            if p.get('ARXIVID', p.get('arxiv_id')) == arxiv_id:
                paper_data = {
                    'arxiv_id': p.get('ARXIVID') or p.get('arxiv_id'),
                    'title': p['title'],
                    'abstract': p['abstract'],
                    'authors': p['authors'],
                    'url': f"https://arxiv.org/abs/{p.get('ARXIVID') or p.get('arxiv_id')}",
                    'comment': p.get('COMMENT') or p.get('comment'),
                    'relevance': p.get('RELEVANCE') or p.get('relevance'),
                    'novelty': p.get('NOVELTY') or p.get('novelty')
                }
                paper = Paper(**paper_data)
                break
        
        if not paper:
            return jsonify({'error': 'Paper not found'})
        
        # Process Q&A
        qa_results = qa_processor.process_qa(paper)
        
        if 'error' in qa_results:
            return jsonify({'error': qa_results['error']})
        
        # Format Q&A with rich formatting
        formatted_content = ""
        for question, answer in qa_results.items():
            # Format each Q&A pair
            qa_section = f"### {question}\n\n{answer}\n\n"
            formatted_content += qa_section
        
        # Process the markdown content
        html_content = md_processor.process_content(formatted_content)
        print(html_content)
        return jsonify({'content': html_content})
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/history')
def history():
    """History page to display all available paper archives"""
    try:
        # Get list of available dates
        available_dates = get_cached_dates()
        
        # Create a dictionary to organize papers by month
        papers_by_month = {}
        
        for date_info in available_dates:
            date_obj = datetime.strptime(date_info['date'], '%Y-%m-%d')
            month_key = date_obj.strftime('%B %Y')
            
            # Load papers for this date
            json_file = f'out/cache/{date_info["date"]}_output.json'
            try:
                with open(json_file, 'r') as f:
                    papers_dict = json.load(f)
                    paper_count = len(papers_dict)
            except:
                paper_count = 0
            
            # Add to papers_by_month dictionary
            if month_key not in papers_by_month:
                papers_by_month[month_key] = []
            
            papers_by_month[month_key].append({
                'date': date_info['date'],
                'display_date': date_info['display_date'],
                'paper_count': paper_count
            })
        
        return render_template('history.html', 
                             papers_by_month=papers_by_month,
                             current_date=datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        print(f"Error in history route: {e}")
        return f"Error loading history: {str(e)}", 500

if __name__ == '__main__':
    # Load API keys from environment or config
    keyconfig = configparser.ConfigParser()
    keyconfig.read("configs/keys.ini")

    # Set up Gemini API key if using Gemini
    GEMINI_API_KEY = keyconfig["GEMINI"]["api_key"]
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    app.run(debug=True)