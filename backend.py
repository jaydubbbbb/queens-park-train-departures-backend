"""
Queens Park Station Departure Scraper - SIMPLE VERSION
Works with ScraperAPI with graceful fallback
"""

from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import os

app = Flask(__name__)
CORS(app)

# Configuration
STATION_URL = 'https://www.transperth.wa.gov.au/Timetables/Live-Train-Times?station=Queens%20Park%20Stn'
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY', '')
TIMEOUT = 60  # Shorter timeout

def parse_time_to_minutes(time_str):
    """Convert time string to minutes from now"""
    if not time_str:
        return None
    
    time_str = time_str.strip().lower()
    
    if 'now' in time_str or 'due' in time_str:
        return 0
    
    # Look for "X min" format
    match = re.search(r'(\d+)\s*min', time_str)
    if match:
        return int(match.group(1))
    
    # Look for time format like "19:34"
    match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        
        now = datetime.now()
        departure = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if departure < now:
            departure += timedelta(days=1)
        
        return int((departure - now).total_seconds() / 60)
    
    return None

def scrape_transperth_simple():
    """Simple scraping with minimal parameters"""
    try:
        if not SCRAPER_API_KEY:
            print("No ScraperAPI key - returning empty")
            return []
        
        # Simpler API call - just render, no wait
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={STATION_URL}&render=true"
        
        print(f"Fetching via ScraperAPI...")
        response = requests.get(api_url, timeout=TIMEOUT)
        
        if response.status_code != 200:
            print(f"ScraperAPI returned status {response.status_code}")
            return []
        
        print("Parsing HTML...")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find table
        table = soup.find('table', id='tblStationStatus')
        if not table:
            print("Table not found")
            return []
        
        tbody = table.find('tbody')
        if not tbody:
            print("tbody not found")
            return []
        
        rows = tbody.find_all('tr')
        print(f"Found {len(rows)} rows")
        
        departures = []
        
        for idx, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # Get time from first cell
                time_text = cells[0].get_text(strip=True, separator=' ').split()[0] if cells[0].get_text(strip=True) else ''
                
                # Get destination from second cell
                dest_text = cells[1].get_text(strip=True)
                
                # Get platform from third cell
                platform = '?'
                if len(cells) >= 3:
                    platform_text = cells[2].get_text(strip=True)
                    match = re.search(r'platform\s+(\d+)', platform_text, re.I)
                    if match:
                        platform = match.group(1)
                
                # Skip if empty
                if not dest_text:
                    continue
                
                # If no time, skip (JavaScript didn't load)
                if not time_text:
                    print(f"Row {idx}: No time for {dest_text}")
                    continue
                
                minutes = parse_time_to_minutes(time_text)
                
                if minutes is not None:
                    departures.append({
                        'platform': platform,
                        'destination': dest_text,
                        'time_display': time_text,
                        'minutes': minutes,
                        'pattern': 'W',
                        'stops': 'All Stations'
                    })
                    print(f"✓ {dest_text} in {minutes} min from platform {platform}")
            
            except Exception as e:
                print(f"Error parsing row {idx}: {e}")
                continue
        
        return departures
    
    except requests.Timeout:
        print("Request timed out")
        return []
    except Exception as e:
        print(f"Error scraping: {e}")
        return []

@app.route('/api/departures', methods=['GET'])
def get_departures():
    """Get all departures"""
    try:
        print("=" * 50)
        all_deps = scrape_transperth_simple()
        print(f"Total found: {len(all_deps)}")
        
        # Separate by direction
        perth = [d for d in all_deps if 'perth' in d['destination'].lower()]
        south = [d for d in all_deps if 'perth' not in d['destination'].lower()]
        
        perth.sort(key=lambda x: x['minutes'])
        south.sort(key=lambda x: x['minutes'])
        
        return jsonify({
            'success': True,
            'perth': perth[:10],
            'south': south[:10],
            'last_updated': datetime.now().isoformat(),
            'using_proxy': bool(SCRAPER_API_KEY)
        })
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'has_api_key': bool(SCRAPER_API_KEY)
    })

@app.route('/')
def index():
    """Info page"""
    status = "✅ API key configured" if SCRAPER_API_KEY else "❌ No API key"
    return f'''
    <html>
        <head><title>Queens Park Station API</title></head>
        <body style="font-family: Arial; padding: 40px; max-width: 600px; margin: 0 auto;">
            <h1>🚆 Queens Park Station API</h1>
            <p><strong>Status:</strong> {status}</p>
            <h2>Endpoints:</h2>
            <ul>
                <li><a href="/api/health">/api/health</a></li>
                <li><a href="/api/departures">/api/departures</a></li>
            </ul>
        </body>
    </html>
    '''

if __name__ == '__main__':
    print("🚆 Queens Park Station API")
    print("=" * 50)
    if SCRAPER_API_KEY:
        print("✅ ScraperAPI configured")
    else:
        print("⚠️ Set SCRAPER_API_KEY environment variable")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
