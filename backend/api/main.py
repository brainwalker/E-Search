from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

# Allow all origins for simplicity, but in a production environment
# you would want to restrict this to your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_session_cookie(url):
    """
    Fetches the session cookie required to access the schedule page.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # The site might have a consent page, so we look for a specific link
        # to the main content if we're not on the schedule page directly.
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # This is a simplified example. The actual site might have a more complex
        # mechanism for age verification and session handling.
        # We assume the initial request gives us the necessary cookies.
        return response.cookies
    except requests.RequestException as e:
        print(f"Error getting session cookie: {e}")
        return None

@app.get("/api/v1/schedule")
def get_schedule():
    """
    Scrapes the escort schedule data from the website.
    """
    schedule_url = "https://www.sexyfriendstoronto.com/toronto-escorts/schedule"
    base_url = "https://www.sexyfriendstoronto.com"
    
    cookies = get_session_cookie(base_url)
    if not cookies:
        return {"error": "Could not obtain session cookie."}

    try:
        response = requests.get(schedule_url, cookies=cookies, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch schedule page: {e}"}

    soup = BeautifulSoup(response.content, 'html.parser')
    
    schedule_data = []
    
    schedule_rows = soup.find_all('div', class_='schedule-row')

    for row in schedule_rows:
        name_tag = row.find('h3')
        if not name_tag:
            continue
            
        name = name_tag.get_text(strip=True)
        
        img_tag = row.find('img')
        # Resolve relative URL to absolute
        image_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else ''
        if image_url and not image_url.startswith('http'):
            image_url = base_url + image_url

        # Extract schedule times
        days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
        schedule = {}
        for day in days:
            day_div = row.find('div', class_=f"time-slot {day}")
            if day_div:
                time_text = day_div.get_text(strip=True)
                schedule[day] = time_text if time_text else "Not Available"
            else:
                schedule[day] = "Not Available"

        schedule_data.append({
            "name": name,
            "imageUrl": image_url,
            "schedule": schedule
        })

    return {"data": schedule_data}
