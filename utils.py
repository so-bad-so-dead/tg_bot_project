import asyncio
import httpx
import aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from functools import lru_cache
from config import API_TOKEN

users = {}

geolocator = Nominatim(user_agent="city_time")
tf = TimezoneFinder()

async def get_user(user_id: int):
    if user_id not in users:
        users[user_id] = {
            "name": 'user'
        }
    return users[user_id]

async def get_water_goal(user_id: int):
    user = users[user_id]
    weight = user['weight']
    activity_level = user['activity_level']
    city = user['city']

    cur_temp = (await fetch_temp_async(city, API_TOKEN))[0][0]
    activity_add = 500 * activity_level / 30
    temp_add = 500 if cur_temp > 25 else 0
    water_norm = weight * 30 + activity_add + temp_add

    return water_norm

async def get_calorie_goal(user_id: int):
    user = users[user_id]
    weight = user['weight']
    height = user['height']
    age = user['age']
    activity_level = user['activity_level']

    activity_add = 300 * activity_level / 60
    water_norm = weight * 10 + 6.25 * height - 5 * age + activity_add

    return water_norm


def _get_date_sync(city: str):
    location = geolocator.geocode(city)
    if not location:
        return None

    timezone = tf.timezone_at(
        lat=location.latitude,
        lng=location.longitude
    )

    if not timezone:
        return None

    return datetime.now(ZoneInfo(timezone)).date()

async def get_current_date(city: str):
    return await asyncio.to_thread(_get_date_sync, city)

async def get_temperature_async(client, city, api_key, print_output=True):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "ru"
    }

    response = await client.get(url, params=params)
    data = response.json()

    if response.status_code == 200:
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        description = data["weather"][0]["description"]
        if print_output:
            print(f"{city}: {temp}°C")
        return temp, feels_like, description
    else:
        print("Ошибка:", data)
        return data

async def fetch_temp_async(city, api_key):
    async with httpx.AsyncClient() as client:
        tasks = [get_temperature_async(client, city, api_key)]
        results = await asyncio.gather(*tasks)
        
    return results

@lru_cache(maxsize=100)
async def get_food_info(product_name: str):
    url = (
        "https://world.openfoodfacts.org/cgi/search.pl"
        f"?action=process&search_terms={product_name}&json=true"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Ошибка: {response.status}")
                return None

            data = await response.json()
            products = data.get("products", [])

            if not products:
                return None

            first_product = products[0]

            return {
                "name": first_product.get("product_name", "Неизвестно"),
                "calories": first_product.get("nutriments", {}).get(
                    "energy-kcal_100g", 0
                ),
            }

