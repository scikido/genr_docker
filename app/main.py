import asyncio
from quart import Quart, request, jsonify
from time import time
import os
import re
import httpx
from telethon.errors import ChannelInvalidError, ChannelPrivateError
from quart_cors import cors
from telethon.sync import TelegramClient
from datetime import datetime
from dotenv import load_dotenv
from pyppeteer import launch

app = Quart(__name__)
app = cors(app, allow_origin="*")  # Allow requests from any origin

load_dotenv()

browser_instance = None
browser_lock = asyncio.Lock()
# path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# path = "/usr/bin/google-chrome"

invalid_channels = set([
    "snatch_team", "spmias", "lbbotnews", "MEzZKwya_dg4ODM1", "x_legacy",
    "S0D", "ck_nt", "ZLcOzVBENZg2ZWRl", "sipvoip", "thehydramarket",
    "durov", "mrrobothackingstuff", "zerodaylaz", "worlddoctorsalliance","AAAAAE1eCVFTLGzOhkU","AAAAAEyTZ0JoovFxE","deepdatamarket","thevirusss","loljsjsjsjssh","6miLWkw70RxjYmE0","ykoIXVJBirI0NzU0","m4nifest0","GvfPnZMWZEMyMDFl","XLi5D7RLLTBmMjM1","cybertrickszone"
])

async def get_browser():
    start_time = time()
    global browser_instance
    async with browser_lock:
        if browser_instance is None:
            print("Launching browser...")
            browser_instance = await launch(
                executablePath=os.getenv("CHROME_BIN"),
                options={"args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-extensions", "--disable-infobars", "--disable-notifications"]}
            )
            print("Browser launched.")
    end_time = time()
    print(f"get_browser took {end_time - start_time} seconds.")
    return browser_instance

async def scrape_page(browser, search_query, page_num):
    start_time = time()
    print(f"Scraping page {page_num} for query '{search_query}'...")
    page = await browser.newPage()
    s_url = f"https://cse.google.com/cse?&cx=006368593537057042503:efxu7xprihg#gsc.tab=0&gsc.q={search_query}&gsc.sort=date&gsc.page={page_num}"
    print(f"Navigating to {s_url}")
    await page.goto(s_url, {"waitUntil": "networkidle2"})
    scraped_links = await page.evaluate(
        """() => {
            const anchorNodes = document.querySelectorAll('a');
            const linksArray = Array.from(anchorNodes);
            const nonEmptyLinks = linksArray
                .filter(link => link.href && link.href.trim() !== '' && !link.href.startsWith('javascript:void(0)'))
                .map(link => link.href);

            return nonEmptyLinks;
        }"""
    )
    await page.close()
    end_time = time()
    print(f"Scraped {len(scraped_links)} links from page {page_num}.")
    print(f"scrape_page took {end_time - start_time} seconds.")
    return scraped_links

async def scrape_links(search_query, num_pages=2):
    start_time = time()
    # print(f"Starting link scraping for query '{search_query}'...")
    browser = await get_browser()

    tasks = [scrape_page(browser, search_query, page_num) for page_num in range(1, num_pages + 1)]
    all_links = await asyncio.gather(*tasks)

    # Flatten the list of lists into a single list
    scraped_links = [link for sublist in all_links for link in sublist]

    end_time = time()
    print(f"Time taken for scraping: {end_time - start_time} seconds")
    return scraped_links

async def extract_tgstat_channel_names(all_links):
    start_time = time()
    print("Extracting TGSTAT channel names...")
    tgstat_channel_names = {
        match.group(1)
        for url in all_links
        if "tgstat.com" in url and (match := re.search(r"@([^/]+)", url))
    }
    end_time = time()
    print(f"TGSTAT Channel Names Fetched: {tgstat_channel_names}")
    print(f"extract_tgstat_channel_names took {end_time - start_time} seconds.")
    return tgstat_channel_names

async def extract_telegram_channel_names(all_links):
    start_time = time()
    print("Extracting Telegram channel names...")
    pattern = re.compile(r"https?://(t\.me|telegram\.me)/s/([^/?]+)(?:\?[^/]+)?$")
    telegram_channel_names = {
        match.group(2) for url in all_links if (match := pattern.search(url))
    }
    end_time = time()
    print(f"Telegram Channel Names Fetched: {telegram_channel_names}")
    print(f"extract_telegram_channel_names took {end_time - start_time} seconds.")
    return telegram_channel_names

async def extract_telemetr_channel_names(all_links):
    start_time = time()
    print("Extracting Telemetr channel names...")
    telemetr_channel_names = {
        match.group(1)
        for url in all_links
        if "telemetr.io" in url
        and (match := re.search(r"telemetr.io/\w+/channels/\d+-(\w+)", url))
    }
    end_time = time()
    print(f"TELEMETR CHANNEL NAMES: {telemetr_channel_names}")
    print(f"extract_telemetr_channel_names took {end_time - start_time} seconds.")
    return telemetr_channel_names

async def retrieve_channel_names(search_query):
    start_time = time()
    try:
        modified_query1 = f'"{search_query}" AND ("malware" OR "c2") AND ("hack" OR "trojan" OR "leak" OR "stealer") -telegraph -news'
        modified_query2 = f'{search_query}'

        # Determine if the search query contains a number
        if any(char.isdigit() for char in search_query):
            use_modified_query2 = True
        else:
            use_modified_query2 = False

        # If use_modified_query2 is True, use modified_query2, else use modified_query1
        if use_modified_query2:
            print("Using modified_query2...")
            all_links = await scrape_links(modified_query2)
        else:
            print("Using modified_query1...")
            all_links = await scrape_links(modified_query1)

        # Extract channel names from the scraped links
        tgstat_channel_names, telegram_channel_names, telemetr_channel_names = await asyncio.gather(
            extract_tgstat_channel_names(all_links),
            extract_telegram_channel_names(all_links),
            extract_telemetr_channel_names(all_links),
        )

        # Combine all channel names
        channel_names = tgstat_channel_names | telegram_channel_names | telemetr_channel_names

        # Filter out invalid channels here
        valid_channel_names = [channel for channel in channel_names if channel not in invalid_channels]

        end_time = time()
        print(f"retrieve_channel_names took {end_time - start_time} seconds.")
        return valid_channel_names
    except Exception as e:
        end_time = time()
        print(f"Error retrieving channel names: {e}")
        print(f"retrieve_channel_names took {end_time - start_time} seconds.")
        return []



async def fetch_messages_from_channel(client, channel_name, keyword, limit=5):
    start_time = time()
    print(f"Fetching messages from channel '{channel_name}' with keyword '{keyword}'...")
    messages_info = []

    try:
        async for message in client.iter_messages(
            channel_name,
            offset_date=datetime.now(),
            reverse=False,
            limit=limit,
            search=keyword,
        ):
            if message.text:
                message_info = {
                    "channel_name": channel_name,
                    "message_id": message.id,
                    "text": message.text,
                    "date": message.date.isoformat(),
                }
                messages_info.append(message_info)

    except ChannelInvalidError:
        print(f"Channel '{channel_name}' is invalid or does not exist.")
        invalid_channels.add(channel_name)
    except ChannelPrivateError:
        print(f"Channel '{channel_name}' is private and cannot be accessed.")
        invalid_channels.add(channel_name)
    except Exception as e:
        print(f"An error occurred with channel '{channel_name}': {e}")
        invalid_channels.add(channel_name)

    end_time = time()
    print(f"Fetched {len(messages_info)} messages from channel '{channel_name}'.")
    print(f"fetch_messages_from_channel took {end_time - start_time} seconds.")
    return messages_info

async def retrieve_telegram_messages(search_query, limit=5):
    start_time = time()
    # print(f"Retrieving Telegram messages for query '{search_query}'...")
    try:
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        channel_names = await retrieve_channel_names(search_query)
        print(f"Time taken to fetch channel names: {time() - start_time} seconds")

        async with TelegramClient("saum", api_id, api_hash) as client:
            tasks = [
                fetch_messages_from_channel(client, channel, search_query, limit)
                for channel in channel_names
            ]
            messages_info = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten the list of lists into a single list and filter out any None or Exception results
        messages_info = [item for sublist in messages_info if isinstance(sublist, list) for item in sublist]
        end_time = time()
        print(f"Time taken to fetch messages: {end_time - start_time} seconds")
        return {
            "messages_info": messages_info,
        }
    except Exception as e:
        end_time = time()
        print(f"Error occurred during message retrieval: {e}")
        print(f"retrieve_telegram_messages took {end_time - start_time} seconds.")
        return {"error": "Internal Server Error telegram"}

@app.route("/")
async def home():
    start_time = time()
    print("Endpoint '/' called.")
    response = jsonify("HELLO FROM GENERIC Search 4th dork")
    end_time = time()
    print(f"home took {end_time - start_time} seconds.")
    return response

@app.route("/api/retrieve-telegram-messages", methods=["POST"])
async def api_retrieve_telegram_messages():
    start_time = time()
    print("Endpoint '/api/retrieve-telegram-messages' called.")
    try:
        form = await request.form
        search_query = form["search_query"]

        print(
            "Telegram Messages retrieved at: ",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        result = await retrieve_telegram_messages(search_query)

        end_time = time()
        print(f"api_retrieve_telegram_messages took {end_time - start_time} seconds.")
        return jsonify(result)
    except Exception as e:
        end_time = time()
        print(f"Error in '/api/retrieve-telegram-messages': {e}")
        print(f"api_retrieve_telegram_messages took {end_time - start_time} seconds.")
        return jsonify({"error": "Internal Server Error"}), 500

