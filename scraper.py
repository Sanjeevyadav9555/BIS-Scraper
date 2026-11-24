import random
import pandas as pd
from datetime import date
from playwright.sync_api import sync_playwright

# Yahan apne cities ki list badal sakte ho
CITIES = {
    "Uttar Pradesh": ["Ghaziabad", "Noida", "Kanpur", "Lucknow"],
    "Delhi": [
  "Narela",
  "Bawana",
  "Mangolpuri",
  "Rohini",
  "Wazirpur",
  "Jhilmil",
  "Anand Parbat",
  "Mayapuri",
  "Naraina",
  "Okhla Phase I",
  "Okhla Phase II",
  "Okhla Phase III",
  "Mundka",
  "Udyog Nagar",
  "Kirti Nagar",
  "Moti Nagar",
  "Mohan Co-operative Industrial Estate",
  "Patparganj",
  "Shahdara",
  "Sahibabad",
  "Loni",
  "Noida",
  "Greater Noida",
  "Gurugram",
  "Faridabad"
],
    "Haryana": ["Gurgaon", "Faridabad", "Panipat"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Rishikesh"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
}

# True = sirf Manufacturer save honge, False = sab save honge
ONLY_MANUFACTURER = True


def classify(raw_category, name):
    """Google ki category / company ke naam se Manufacturer, Wholesaler, Store ya Unclear batata hai."""
    rules = [
        ("Manufacturer", ["manufactur", "factory", "fabricat", "producer",
                          "industries", "industry", "mills", "works"]),
        ("Wholesaler", ["wholesal", "distributor", "supplier", "dealer",
                        "trader", "trading", "exporter", "importer"]),
        ("Store", ["store", "shop", "showroom", "retail", "mart", "outlet"]),
    ]
    # Pehle Google ki category dekho (zyada reliable), phir company ka naam
    for text in ((raw_category or "").lower(), (name or "").lower()):
        for label, keywords in rules:
            if any(k in text for k in keywords):
                return label
    return "Unclear"


def scrape_city(page, product, city, state, max_results):
    query = f"{product} manufacturer in {city}, {state}"
    url = "https://www.google.com/maps/search/" + query.replace(" ", "+")
    rows = []

    page.goto(url)
    page.wait_for_timeout(5000)

    try:
        page.click("button:has-text('Accept all')", timeout=3000)
    except Exception:
        pass

    feed = page.locator('div[role="feed"]')
    try:
        feed.wait_for(timeout=15000)
    except Exception:
        print(f"  {city}: koi result nahi")
        return rows

    last_count = 0
    for _ in range(15):
        feed.evaluate("el => el.scrollBy(0, 3000)")
        page.wait_for_timeout(2000)
        count = page.locator("a.hfpxzc").count()
        if count >= max_results or count == last_count:
            break
        last_count = count

    links = page.locator("a.hfpxzc")
    total = min(links.count(), max_results)
    print(f"  {city}: {total} listings")

    for i in range(total):
        try:
            links.nth(i).click()
            page.wait_for_timeout(random.randint(2500, 4000))

            name = page.locator("h1.DUwDvf").first.inner_text(timeout=5000)

            # Category pehle nikaal ke check karo, taaki non-manufacturer par time waste na ho
            cat_el = page.locator("button.DkEaL")
            raw_category = cat_el.first.inner_text(timeout=2000) if cat_el.count() else ""
            category = classify(raw_category, name)

            if ONLY_MANUFACTURER and category != "Manufacturer":
                print(f"    {i + 1}. {name}  [{category}] -> skip")
                continue

            def get(selector):
                el = page.locator(selector)
                return el.first.get_attribute("aria-label") if el.count() else ""

            address = get('button[data-item-id="address"]')
            phone = get('button[data-item-id^="phone"]')
            site_el = page.locator('a[data-item-id="authority"]')
            website = site_el.first.get_attribute("href") if site_el.count() else ""

            rows.append({
                "Company Name": name,
                "Product": product,
                "Category": category,
                "Google Category": raw_category,
                "Website": website,
                "Contact No": (phone or "").replace("Phone:", "").strip(),
                "Location": (address or "").replace("Address:", "").strip(),
                "City": city,
                "State": state,
                # Calling tracker columns
                "Call Date": "",
                "Interested (Y/N/Later)": "",
            })
            print(f"    {i + 1}. {name}  [{category}] -> saved")
        except Exception as e:
            print(f"    Skip {i + 1}: {e}")

    return rows


def save(all_rows, filename):
    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["Company Name", "Contact No"])
    df.to_excel(filename, index=False)
    return len(df)


if __name__ == "__main__":
    product = input("Product name dalo: ").strip()
    state = input("State dalo: ").strip()
    max_results = int(input("Har shehar se kitne results (e.g. 20): ") or 20)

    cities = CITIES.get(state)
    if not cities:
        cities = [c.strip() for c in input(
            "State list me nahi hai. Cities comma se dalo: ").split(",")]

    filename = f"{product}_{state}_{date.today()}.xlsx".replace(" ", "_")
    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(locale="en-IN")

        for city in cities:
            print(f"\n{city} shuru...")
            all_rows += scrape_city(page, product, city, state, max_results)
            if all_rows:
                n = save(all_rows, filename)  # har shehar ke baad save
                print(f"  Saved: {n} unique companies abhi tak")
            page.wait_for_timeout(random.randint(5000, 9000))

        browser.close()

    print(f"\nKhatam. File: {filename}")