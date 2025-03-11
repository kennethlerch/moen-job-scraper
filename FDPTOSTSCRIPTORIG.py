from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import time
import re

### ✅ SETUP SELENIUM ###
options = Options()
options.add_argument("--headless")  # Run Chrome in headless mode
options.add_argument("--no-sandbox")  # Bypass OS security model
options.add_argument("--disable-dev-shm-usage")  # Prevent memory issues
options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# ✅ Start ChromeDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# ✅ Open login page
driver.get("https://pro.proconnect.com/login")
time.sleep(10)

# ✅ Click "Sign In" button
try:
    sign_in_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "button-interactive"))
    )
    sign_in_button.click()
    print("✅ Clicked 'Sign In' button!")
    time.sleep(3)
except Exception:
    print("❌ Failed to click 'Sign In' button!")

# ✅ Enter login credentials
try:
    username_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "loginId"))
    )
    password_field = driver.find_element(By.ID, "password")
    login_button = driver.find_element(By.ID, "login-btn")

    username_field.send_keys("office@gardnerplumbingco.com")
    password_field.send_keys("Job13:14!")
    login_button.click()
    print("✅ Entered login credentials and clicked 'Log In'!")
    time.sleep(60)
except Exception:
    print("❌ Failed to enter credentials!")

# ✅ Wait for jobs page to load
try:
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    print("✅ Assuming jobs page is loaded!")
except Exception:
    print("❌ Jobs page did not load in time.")

### ✅ FIND "ASSIGN PRO" JOBS & CLICK TO OPEN ###
jobs_data = []
base_url = "https://pro.proconnect.com/jobs"

# ✅ Refresh the page source
driver.get(base_url)
time.sleep(5)

def get_job_list():
    """ Re-fetches the job elements to avoid stale element errors """
    return driver.find_elements(By.XPATH, "//div[contains(@class, '_statusPill_dzcst_42') and contains(text(), 'Assign Pro')]")

job_elements = get_job_list()

for index in range(len(job_elements)):
    try:
        job_elements = get_job_list()
        job_status = job_elements[index]
        job_entry = job_status.find_element(By.XPATH, "./ancestor::div[contains(@data-testid, 'appointment-list-item')]")
        job_entry.click()
        time.sleep(5)

        def extract_text_with_js(xpath):
            """ Extracts text using JavaScript execution """
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                text = driver.execute_script("return arguments[0].innerText;", element).strip()
                return text if text else "N/A"
            except Exception:
                return "N/A"

        # ✅ Extract Data
        job_service = extract_text_with_js("//div[@id='jobPage.jobDetails']//div[h6[contains(text(), 'Service:')]]").replace("Service:", "").strip()
        job_work_order = extract_text_with_js("//div[@id='jobPage.jobDetails']//div[h6[contains(text(), 'Work Order:')]]").replace("Work Order:", "").strip()
        customer_name = extract_text_with_js("//div[@id='jobPage.customerInfo']//div[h6[contains(text(), 'Name:')]]").replace("Name:", "").strip()
        customer_phone = extract_text_with_js("//div[@id='jobPage.customerInfo']//div[h6[contains(text(), 'Phone:')]]").replace("Phone:", "").strip()
        job_description = extract_text_with_js("//div[@id='jobPage.description']//div[contains(@class, 'text-body-long')]")

        appointment_date = extract_text_with_js("//div[@data-testid='jobDetail.appointmentTime']//div[1]")
        appointment_time = extract_text_with_js("//div[@data-testid='jobDetail.appointmentTime']//div[2]")

        street_address = extract_text_with_js("//div[@data-testid='address.street']")
        city_state_zip = extract_text_with_js("//div[contains(@class, '_cityStateZip')]")

        # ✅ Split city, state, and zip
        match = re.match(r"(.+),\s([A-Z]{2})\s(\d{5})", city_state_zip)
        if match:
            city, state, zip_code = match.groups()
        else:
            city, state, zip_code = "N/A", "N/A", "N/A"

        # ✅ Append Data
        jobs_data.append({
            "Service": job_service,
            "Work Order": job_work_order,
            "Name": customer_name,
            "Phone": customer_phone,
            "Street Address": street_address,
            "City": city,
            "State": state,
            "ZIP": zip_code,
            "Country": "US",
            "Appointment Date": appointment_date,
            "Appointment Time": appointment_time,
            "Job Description": job_description
        })

        print(f"✅ Extracted details: {customer_name} - {customer_phone}")

        # ✅ Return to job listings
        driver.get(base_url)
        time.sleep(5)

    except Exception as e:
        print(f"⚠️ Error processing job {index+1}: {e}")

### ✅ GOOGLE SHEETS INTEGRATION ###
SERVICE_ACCOUNT_FILE = "front-door-pro-service-pro-8c1d8344b734.json"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
client = gspread.authorize(creds)

SHEET_NAME = "AcceptedJobsFDPtoST"
SHEET_TAB = "ASSIGNPROJOBS"

sheet = client.open(SHEET_NAME).worksheet(SHEET_TAB)

# ✅ Load existing Work Orders for duplicate check
existing_jobs = sheet.get_all_records()
existing_work_orders = {row["Work Order"] for row in existing_jobs if "Work Order" in row}

# ✅ Filter only new jobs
new_jobs_data = [job for job in jobs_data if job["Work Order"] not in existing_work_orders]

if new_jobs_data:
    new_jobs_df = pd.DataFrame(new_jobs_data)
    sheet.append_rows(new_jobs_df.values.tolist())
    print(f"✅ {len(new_jobs_df)} new 'Assign Pro' jobs added to Google Sheets!")
else:
    print("⚠️ No new 'Assign Pro' jobs found.")

driver.quit()




