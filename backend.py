"""
Transperth Station Departure Scraper - FIXED VERSION
Now with complete browser headers including sec-ch-ua client hints
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from urllib.parse import urlencode
import time

app = Flask(__name__)
CORS(app)

# Perth timezone (UTC+8)
try:
    from zoneinfo import ZoneInfo
    PERTH_TZ = ZoneInfo('Australia/Perth')
except ImportError:
    from datetime import timezone, timedelta
    PERTH_TZ = timezone(timedelta(hours=8))

# Transperth URLs
LIVE_TIMES_URL = "https://www.transperth.wa.gov.au/Timetables/Live-Train-Times"
API_URL = "https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetStopTimetable"

# Persistent session
SESSION = None
TOKEN_CACHE = {
    'verification_token': None,
    'module_id': '5111',
    'tab_id': '248',
    'timestamp': None
}

def get_session():
    """Get or create a persistent session with complete browser headers"""
    global SESSION
    if SESSION is None:
        SESSION = requests.Session()
        # Complete Chrome 122 headers including Client Hints
        SESSION.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Cache-Control': 'max-age=0'
        })
    return SESSION

def fetch_page_tokens():
    """Fetch the verification token from the page"""
    try:
        print("\n" + "="*60)
        print("FETCHING PAGE TOKENS")
        print("="*60)
        
        session = get_session()
        
        print(f"→ GET {LIVE_TIMES_URL}")
        response = session.get(LIVE_TIMES_URL, timeout=15)
        
        print(f"← Status: {response.status_code}")
        
        if response.status_code == 403:
            print("\n❌ 403 FORBIDDEN")
            return None
        
        if response.status_code != 200:
            print(f"❌ Failed: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find RequestVerificationToken
        token_input = soup.find('input', {'name': '__RequestVerificationToken'})
        if token_input:
            verification_token = token_input.get('value')
        else:
            token_meta = soup.find('meta', {'name': '__RequestVerificationToken'})
            verification_token = token_meta.get('content') if token_meta else None
        
        if verification_token:
            print(f"✅ Token: {verification_token[:30]}...")
            print(f"✅ Cookies: {len(session.cookies)} cookie(s)")
            
            # Print cookie names for debugging
            cookie_names = [cookie.name for cookie in session.cookies]
            print(f"✅ Cookie names: {', '.join(cookie_names)}")
            
            return {
                'verification_token': verification_token,
                'module_id': '5111',
                'tab_id': '248',
                'timestamp': datetime.now()
            }
        else:
            print("❌ Could not find verification token")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_tokens():
    """Get tokens from cache or fetch new ones"""
    if TOKEN_CACHE['timestamp']:
        age = (datetime.now() - TOKEN_CACHE['timestamp']).total_seconds()
        if age < 300 and TOKEN_CACHE['verification_token']:  # 5 minutes
            print("ℹ Using cached tokens")
            return TOKEN_CACHE
    
    tokens = fetch_page_tokens()
    if tokens:
        TOKEN_CACHE.update(tokens)
    
    return TOKEN_CACHE

def calculate_minutes_until(depart_time_str):
    """Calculate minutes until departure"""
    try:
        depart_time = datetime.fromisoformat(depart_time_str)
        if depart_time.tzinfo is None:
            depart_time = depart_time.replace(tzinfo=PERTH_TZ)
        now = datetime.now(PERTH_TZ)
        diff = (depart_time - now).total_seconds() / 60
        return max(0, int(diff))
    except Exception as e:
        return None

def fetch_all_departures(station_id='133'):
    """Fetch all departures for specified station"""
    try:
        print("\n" + "="*60)
        print(f"FETCHING DEPARTURES FOR STATION {station_id}")
        print("="*60)
        
        # Get tokens
        tokens = get_tokens()
        
        if not tokens.get('verification_token'):
            print("❌ No verification token available")
            return []
        
        session = get_session()
        
        # Prepare data
        now = datetime.now()
        search_date = now.strftime('%Y-%m-%d')
        search_time = now.strftime('%H:%M')
        
        form_data = {
            'StationId': station_id,
            'SearchDate': search_date,
            'SearchTime': search_time,
            'IsRealTimeChecked': 'true'
        }
        
        # Complete headers for API call - matching your browser exactly
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'DNT': '1',
            'Origin': 'https://www.transperth.wa.gov.au',
            'Referer': f'https://www.transperth.wa.gov.au/Timetables/Live-Train-Times',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest',
            'RequestVerificationToken': tokens['verification_token'],
            'ModuleId': tokens['module_id'],
            'TabId': tokens['tab_id'],
            'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        
        print(f"→ POST {API_URL}")
        print(f"  Station: {station_id}, Time: {search_time}")
        print(f"  Token: {tokens['verification_token'][:30]}...")
        
        response = session.post(
            API_URL,
            data=urlencode(form_data),
            headers=headers,
            timeout=15
        )
        
        print(f"← Status: {response.status_code}")
        
        if response.status_code == 403:
            print("\n❌ 403 FORBIDDEN on API call")
            print("Even with complete headers, still blocked.")
            print("This might be IP-based or cookie-based blocking.")
            return []
        
        if response.status_code != 200:
            print(f"❌ API returned {response.status_code}")
            print(f"Response: {response.text[:300]}")
            return []
        
        try:
            data = response.json()
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
            return []
        
        if data.get('result') != 'success':
            print(f"❌ API result: {data.get('result')}")
            print(f"Full response: {data}")
            return []
        
        trips = data.get('trips', [])
        print(f"✅ Found {len(trips)} trips")
        
        departures = []
        
        for trip in trips:
            try:
                stop_name = trip.get('StopTimetableStop', {}).get('Name', '')
                platform_match = re.search(r'Platform\s+(\d+(?:/\d+)?)', stop_name)
                platform = platform_match.group(1) if platform_match else '?'
                
                summary = trip.get('Summary', {})
                headsign = summary.get('Headsign', '')
                direction = summary.get('Direction', '0')
                
                display_title = trip.get('DisplayTripTitle', '')
                countdown = trip.get('DisplayTripStatusCountDown', '')
                
                route_name = summary.get('RouteName', '')
                
                real_time_info = summary.get('RealTimeInfo', {})
                series = real_time_info.get('Series', 'W')
                num_cars = real_time_info.get('NumCars', '')
                fleet_number = real_time_info.get('FleetNumber', '')
                
                depart_time = trip.get('DepartTime', '')
                minutes = calculate_minutes_until(depart_time)
                
                if minutes is None:
                    continue
                
                stops = "All Stations"
                if num_cars:
                    stops = f"{stops} ({num_cars} cars)"
                if series:
                    stops = f"{stops} - {series} series"
                
                departures.append({
                    'platform': platform,
                    'destination': display_title or headsign,
                    'time_display': countdown,
                    'minutes': minutes,
                    'pattern': series or 'W',
                    'stops': stops,
                    'route': route_name,
                    'direction': direction,
                    'fleetNumber': fleet_number
                })
                
            except Exception as e:
                continue
        
        return departures
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/api/departures', methods=['GET'])
def get_departures():
    """Get all departures for specified station"""
    try:
        station_id = request.args.get('station_id', '133')
        
        all_deps = fetch_all_departures(station_id)
        
        perth = [d for d in all_deps if d.get('direction') == '0']
        south = [d for d in all_deps if d.get('direction') == '1']
        
        perth.sort(key=lambda x: x['minutes'])
        south.sort(key=lambda x: x['minutes'])
        
        return jsonify({
            'success': True,
            'perth': perth[:10],
            'south': south[:10],
            'station_id': station_id,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/test', methods=['GET'])
def test_connection():
    """Quick test"""
    print("\n" + "="*60)
    print("RUNNING TEST")
    print("="*60)
    
    # Test page access
    session = get_session()
    response = session.get(LIVE_TIMES_URL, timeout=10)
    
    page_ok = response.status_code == 200
    
    # Test token extraction
    tokens = fetch_page_tokens() if page_ok else None
    token_ok = bool(tokens and tokens.get('verification_token'))
    
    # Test API call
    deps = fetch_all_departures('133') if token_ok else []
    api_ok = len(deps) > 0
    
    result = {
        'page_access': {'status': response.status_code, 'ok': page_ok},
        'token_extraction': {'ok': token_ok},
        'api_call': {'ok': api_ok, 'departures': len(deps)},
        'overall': 'working' if (page_ok and token_ok and api_ok) else 'blocked'
    }
    
    return jsonify(result)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/')
def index():
    """Info page"""
    return '''
    <html>
        <head><title>Transperth API</title></head>
        <body style="font-family: Arial; padding: 40px; max-width: 700px; margin: 0 auto;">
            <h1>🚆 Transperth Live Departures API</h1>
            <p><strong>Status:</strong> Running with complete browser headers</p>
            <h2>Endpoints:</h2>
            <ul>
                <li><a href="/api/health">/api/health</a> - Health check</li>
                <li><a href="/api/test">/api/test</a> - Test if working</li>
                <li><a href="/api/departures?station_id=133">/api/departures</a> - Get departures</li>
            </ul>
        </body>
    </html>
    '''

if __name__ == '__main__':
    print("🚆 Transperth API - COMPLETE HEADERS VERSION")
    print("="*60)
    print("Now includes sec-ch-ua client hints")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)
