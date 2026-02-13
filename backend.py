"""
Queens Park Station Departure Scraper - WITH PROXY SUPPORT
This version can use ScraperAPI or similar services to bypass restrictions

To use ScraperAPI (free tier: 1000 requests/month):
1. Sign up at https://www.scraperapi.com
2. Get your API key
3. Set environment variable: SCRAPER_API_KEY=your_key_here
4. Or paste your key in the code below
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os

app = Flask(__name__)
CORS(app)

# Transperth URLs
URLS = {
    'armadale': 'https://www.transperth.wa.gov.au/Timetables/Live-Train-Times?line=Armadale%20Line&station=Queens%20Park%20Stn',
    'thornlie': 'https://www.transperth.wa.gov.au/Timetables/Live-Train-Times?line=Thornlie-Cockburn%20Line&station=Queens%20Park%20Stn'
}

# ScraperAPI configuration (optional but recommended)
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY', '')  # Set this in Render environment variables

def parse_departure_time(time_str):
    """Convert time string to minutes from now"""
    time_str = time_str.strip().lower()
    
    if 'now' in time_str or 'due' in time_str:
        return 0
    
    match = re.search(r'(\d+)', time_str)
    if match:
        return int(match.group(1))
    
    time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        now = datetime.now()
        departure = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if departure < now:
            from datetime import timedelta
            departure += timedelta(days=1)
        
        diff = (departure - now).total_seconds() / 60
        return int(diff)
    
    return None

def scrape_with_proxy(url):
    """Fetch URL using ScraperAPI proxy"""
    if SCRAPER_API_KEY:
        proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&render=true"
        response = requests.get(proxy_url, timeout=30)
        return response
    return None

def scrape_direct(url):
    """Direct fetch with enhanced headers"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-AU,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.transperth.wa.gov.au/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    session = requests.Session()
    return session.get(url, headers=headers, timeout=15)

def scrape_transperth(url, line_name):
    """Scrape departure information from Transperth website"""
    try:
        # Try proxy first if available
        if SCRAPER_API_KEY:
            print(f"Using ScraperAPI proxy for {line_name}")
            response = scrape_with_proxy(url)
        else:
            print(f"Direct fetch for {line_name}")
            response = scrape_direct(url)
        
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        departures = []
        
        # Find the table with ID tblStationStatus
        table = soup.find('table', id='tblStationStatus')
        
        if not table:
            print(f"Could not find tblStationStatus table for {line_name}")
            return []
        
        # Find the tbody
        tbody = table.find('tbody')
        if not tbody:
            print(f"Could not find tbody in table for {line_name}")
            return []
        
        # Get all rows
        rows = tbody.find_all('tr')
        print(f"Found {len(rows)} departure rows for {line_name}")
        
        for row in rows:
            try:
                # Get all td elements
                tds = row.find_all('td')
                
                if len(tds) < 3:
                    continue
                
                # First td contains time (with footable-first-column class)
                time_td = tds[0]
                time_span = time_td.find('span', class_='footable-toggle')
                if time_span:
                    time_text = time_span.get_text(strip=True)
                else:
                    time_text = time_td.get_text(strip=True).split('\n')[0].strip()
                
                # Second td contains destination
                dest_td = tds[1]
                destination_text = dest_td.get_text(strip=True)
                
                # Third td contains platform info
                platform_td = tds[2]
                platform_spans = platform_td.find_all('span', style=re.compile('display:inline-block'))
                
                platform_text = '?'
                stops_text = 'All Stations'
                
                if platform_spans and len(platform_spans) > 0:
                    # First span usually has "from platform X"
                    platform_info = platform_spans[0].get_text(strip=True)
                    platform_match = re.search(r'platform\s+(\d+)', platform_info, re.I)
                    if platform_match:
                        platform_text = platform_match.group(1)
                    
                    # Additional spans may have stops info
                    if len(platform_spans) > 1:
                        stops_text = platform_spans[1].get_text(strip=True)
                
                # Parse time
                minutes = parse_departure_time(time_text)
                
                if minutes is not None and destination_text:
                    departures.append({
                        'platform': platform_text,
                        'destination': destination_text,
                        'time_display': time_text,
                        'minutes': minutes,
                        'pattern': 'W',
                        'stops': stops_text,
                        'line': line_name
                    })
                    print(f"Parsed: {destination_text} from platform {platform_text} in {minutes} min ({time_text})")
                    
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue
        
        return departures
    
    except requests.RequestException as e:
        print(f"Network error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"Error processing departures: {e}")
        return []

@app.route('/api/departures', methods=['GET'])
def get_departures():
    """API endpoint to get all departures"""
    try:
        print("Fetching departures...")
        armadale_departures = scrape_transperth(URLS['armadale'], 'Armadale')
        thornlie_departures = scrape_transperth(URLS['thornlie'], 'Thornlie-Cockburn')
        
        all_departures = armadale_departures + thornlie_departures
        print(f"Total departures found: {len(all_departures)}")
        
        # Separate by direction
        perth_departures = [
            d for d in all_departures 
            if 'perth' in d['destination'].lower()
        ]
        
        south_departures = [
            d for d in all_departures 
            if d not in perth_departures
        ]
        
        perth_departures.sort(key=lambda x: x['minutes'])
        south_departures.sort(key=lambda x: x['minutes'])
        
        return jsonify({
            'success': True,
            'perth': perth_departures[:10],
            'south': south_departures[:10],
            'last_updated': datetime.now().isoformat(),
            'using_proxy': bool(SCRAPER_API_KEY)
        })
    
    except Exception as e:
        print(f"Error in get_departures: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'proxy_enabled': bool(SCRAPER_API_KEY)
    })

@app.route('/')
def index():
    """Serve info page"""
    proxy_status = "✅ Enabled" if SCRAPER_API_KEY else "❌ Disabled (may have access issues)"
    return f'''
    <html>
        <head><title>Queens Park Station API</title></head>
        <body style="font-family: Arial; padding: 40px; max-width: 600px; margin: 0 auto;">
            <h1>🚆 Queens Park Station API</h1>
            <p><strong>Status:</strong> Running</p>
            <p><strong>Proxy:</strong> {proxy_status}</p>
            <h2>Endpoints:</h2>
            <ul>
                <li><a href="/api/health">/api/health</a> - Health check</li>
                <li><a href="/api/departures">/api/departures</a> - Get departures</li>
            </ul>
            <h2>Setup Proxy (Recommended):</h2>
            <ol>
                <li>Sign up at <a href="https://www.scraperapi.com">ScraperAPI</a> (1000 free requests/month)</li>
                <li>Copy your API key</li>
                <li>In Render: Go to Environment → Add SCRAPER_API_KEY</li>
                <li>Restart your service</li>
            </ol>
        </body>
    </html>
    '''

if __name__ == '__main__':
    print("🚆 Queens Park Station Departure API")
    print("=" * 50)
    if SCRAPER_API_KEY:
        print("✅ ScraperAPI proxy enabled")
    else:
        print("⚠️  No proxy - may face access restrictions")
        print("   Consider setting SCRAPER_API_KEY environment variable")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
