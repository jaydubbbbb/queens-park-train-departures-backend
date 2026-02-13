"""
Queens Park Station Departure Scraper - LIGHTWEIGHT VERSION
Uses requests-html which has built-in JavaScript rendering without external services

Install: pip install requests-html
"""

from flask import Flask, jsonify
from flask_cors import CORS
from requests_html import HTMLSession
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

# Transperth URL
STATION_URL = 'https://www.transperth.wa.gov.au/Timetables/Live-Train-Times?station=Queens%20Park%20Stn'

def parse_departure_time(time_str):
    """Convert time string to minutes from now"""
    if not time_str:
        return None
        
    time_str = time_str.strip().lower()
    
    if 'now' in time_str or 'due' in time_str:
        return 0
    
    match = re.search(r'(\d+)\s*min', time_str)
    if match:
        return int(match.group(1))
    
    match = re.search(r'^(\d+)$', time_str)
    if match:
        return int(match.group(1))
    
    time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        
        if 'pm' in time_str and hour < 12:
            hour += 12
        elif 'am' in time_str and hour == 12:
            hour = 0
        
        now = datetime.now()
        departure = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if departure < now:
            from datetime import timedelta
            departure += timedelta(days=1)
        
        diff = (departure - now).total_seconds() / 60
        return int(diff)
    
    return None

def scrape_transperth():
    """Scrape departure information using requests-html"""
    try:
        print("Creating session...")
        session = HTMLSession()
        
        print(f"Fetching {STATION_URL}")
        response = session.get(STATION_URL, timeout=30)
        
        print("Rendering JavaScript...")
        # Render JavaScript and wait for content
        response.html.render(timeout=20, wait=5, sleep=2)
        
        print("Parsing HTML...")
        departures = []
        
        # Find the table
        table = response.html.find('#tblStationStatus', first=True)
        
        if not table:
            print("Could not find tblStationStatus table")
            return []
        
        # Find all rows in tbody
        rows = table.find('tbody tr')
        print(f"Found {len(rows)} rows")
        
        for idx, row in enumerate(rows):
            try:
                # Get all cells
                cells = row.find('td')
                
                if len(cells) < 2:
                    continue
                
                # Extract time (first cell)
                time_text = cells[0].text.strip().split('\n')[0].strip()
                
                # Extract destination (second cell)
                dest_text = cells[1].text.strip()
                
                # Extract platform (third cell if exists)
                platform = '?'
                stops = 'All Stations'
                
                if len(cells) >= 3:
                    platform_text = cells[2].text
                    match = re.search(r'platform\s+(\d+)', platform_text, re.I)
                    if match:
                        platform = match.group(1)
                    
                    # Extract stops info
                    parts = platform_text.split('\n')
                    if len(parts) > 1:
                        stops = parts[1].strip()
                
                print(f"Row {idx}: time='{time_text}', dest='{dest_text}', platform={platform}")
                
                if not time_text or not dest_text:
                    continue
                
                minutes = parse_departure_time(time_text)
                
                if minutes is not None:
                    departures.append({
                        'platform': platform,
                        'destination': dest_text,
                        'time_display': time_text,
                        'minutes': minutes,
                        'pattern': 'W',
                        'stops': stops
                    })
                    print(f"✓ Added: {dest_text} in {minutes} min")
                
            except Exception as e:
                print(f"Error parsing row {idx}: {e}")
                continue
        
        session.close()
        return departures
        
    except Exception as e:
        print(f"Error scraping: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/api/departures', methods=['GET'])
def get_departures():
    """API endpoint to get all departures"""
    try:
        print("=" * 50)
        print("Fetching departures...")
        
        all_departures = scrape_transperth()
        
        print(f"Total departures found: {len(all_departures)}")
        
        # Separate by direction
        perth_departures = [
            d for d in all_departures 
            if 'perth' in d['destination'].lower()
        ]
        
        south_departures = [
            d for d in all_departures 
            if 'perth' not in d['destination'].lower()
        ]
        
        perth_departures.sort(key=lambda x: x['minutes'])
        south_departures.sort(key=lambda x: x['minutes'])
        
        return jsonify({
            'success': True,
            'perth': perth_departures[:10],
            'south': south_departures[:10],
            'last_updated': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in get_departures: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/')
def index():
    """Serve info page"""
    return '''
    <html>
        <head><title>Queens Park Station API</title></head>
        <body style="font-family: Arial; padding: 40px; max-width: 600px; margin: 0 auto;">
            <h1>🚆 Queens Park Station API</h1>
            <p><strong>Status:</strong> Running (requests-html version)</p>
            <h2>Endpoints:</h2>
            <ul>
                <li><a href="/api/health">/api/health</a> - Health check</li>
                <li><a href="/api/departures">/api/departures</a> - Get departures</li>
            </ul>
            <p><strong>Note:</strong> This version uses requests-html for JavaScript rendering. No external API needed!</p>
        </body>
    </html>
    '''

if __name__ == '__main__':
    print("🚆 Queens Park Station Departure API")
    print("=" * 50)
    print("Using requests-html for JavaScript rendering")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
