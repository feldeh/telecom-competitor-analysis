from utils import save_to_json, check_request, save_scraping_log
from data_model import Products
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
import re
import time
import logging
import traceback
from airflow import AirflowException
from pydantic import ValidationError
from utils import *


URL = {
    'mobile_prepaid': 'https://mobilevikings.be/en/offer/prepaid/',
    'mobile_subscription': 'https://mobilevikings.be/en/offer/subscriptions/',
    'internet_subscription': 'https://mobilevikings.be/en/offer/internet/',
    'combo': 'https://mobilevikings.be/en/offer/combo/'
}


def goto_page(browser, url):

    check_request(url)

    page = browser.new_page()
    logging.info(f"Navigating to URL: {url}")
    page.goto(url, wait_until='domcontentloaded')

    try:
        page.wait_for_selector('#btn-accept-cookies')
        page.query_selector('#btn-accept-cookies').click(force=True)

        return page

    except Exception as e:
        error_message = f"Accept cookie button error: {str(e)}"
        logging.error(error_message)
        raise AirflowException(error_message)


def extract_prepaid_selector_data(page_content, url):
    prepaid_data = []
    date = time.strftime("%Y-%m-%d")
    soup = BeautifulSoup(page_content, 'html.parser')

    prepaid_elements = soup.select('.PrepaidSelectorProduct')

    for prepaid_element in prepaid_elements:
        try:
            prepaid_rates_major = prepaid_element.select('.PrepaidSelectorProduct__rates__major')
            sms = prepaid_rates_major[2].get_text().lower()
            data_focus = prepaid_element['data-focus']
            data = prepaid_element['data-gb']
            minutes = prepaid_element['data-min']
            price = prepaid_element['data-price']

            sms = unlimited_check_to_float(sms)
            minutes = unlimited_check_to_float(minutes)

            prepaid_data.append({
                'product_name': f"mobile_prepaid_{data_focus}_{data}_gb",
                'competitor_name': 'mobileviking',
                'product_category': 'mobile_prepaid',
                'product_url': url,
                'price': float(price),
                'scraped_at': date,
                'data': float(data),
                'minutes': minutes,
                'sms': sms,
                'upload_speed': None,
                'download_speed': None,
            })

            return prepaid_data

        except Exception as e:
            error_message = f"Error extracting prepaid selector data: {str(e)}"
            logging.error(error_message)
            traceback.print_exc()
            raise AirflowException(error_message)


def activate_toggles(page):
    try:
        toggles = page.query_selector_all('.slider')
        for i in range(len(toggles)):
            toggles[i].click()
    except Exception as e:
        error_message = f"Error activating toggles: {str(e)}"
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def extract_prepaid_data(page, url):
    page_content = page.content()
    prepaid_data = extract_prepaid_selector_data(page_content, url)
    activate_toggles(page)

    page_content = page.content()
    prepaid_data_calls = extract_prepaid_selector_data(page_content, url)
    prepaid_data.extend(prepaid_data_calls)

    return prepaid_data


def extract_subscription_data(page_content, url):
    subscription_data = []
    date = time.strftime("%Y-%m-%d")

    try:
        soup = BeautifulSoup(page_content, 'html.parser')
        subscription_elements = soup.select('.PostpaidOption')

        for subscription_element in subscription_elements:

            mobile_data = subscription_element.select_one('.data-amount').get_text().lower().replace('gb', '').strip()
            calls_texts = subscription_element.select_one('.PostpaidOption__voiceTextAmount').get_text().lower()
            price_per_month = subscription_element.select_one('.monthlyPrice__price').get_text().strip().replace(',-', '')

            minutes_match = re.search(r'(\d+) minutes', calls_texts)
            sms_match = re.search(r'(\d+) texts', calls_texts)

            minutes = float(minutes_match.group(1)) if minutes_match else -1
            sms = int(sms_match.group(1)) if sms_match else -1

            subscription_data.append({
                'product_name': f"mobile_subscription_{mobile_data}_gb",
                'competitor_name': 'mobileviking',
                'product_category': 'mobile_subscription',
                'product_url': url,
                'price': float(price_per_month),
                'scraped_at': date,
                'data': float(mobile_data),
                'minutes': minutes,
                'sms': sms,
                'upload_speed': None,
                'download_speed': None,
            })

        return subscription_data

    except Exception as e:
        error_message = f"Error extracting subscription data: {str(e)}"
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def extract_internet_table_data(page_content, url):
    soup = BeautifulSoup(page_content, 'html.parser')
    date = time.strftime("%Y-%m-%d")

    internet_data = {}

    try:
        price = soup.select_one('tr.matrix__price td').get_text().strip()
        cleaned_price = price.replace(',-', '')

        monthly_data = soup.select_one('tr.matrix__data td').get_text().lower()

        download_speed = soup.select_one('tr.matrix__downloadSpeed td').get_text().encode('ascii', 'ignore').decode('ascii').lower().strip()
        upload_speed = soup.select_one('tr.matrix__voice td').get_text().encode('ascii', 'ignore').decode('ascii').lower().strip()

        monthly_data = unlimited_check_to_float(monthly_data)

        internet_data['competitor_name'] = 'mobileviking'
        internet_data['product_category'] = 'internet_subscription'
        internet_data['product_url'] = url
        internet_data['price'] = float(cleaned_price)
        internet_data['scraped_at'] = date
        internet_data['data'] = monthly_data
        internet_data['minutes'] = None
        internet_data['sms'] = None
        internet_data['download_speed'] = download_speed
        internet_data['upload_speed'] = upload_speed

        return internet_data

    except Exception as e:
        error_message = f"Error extracting internet table data: {str(e)}"
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def extract_internet_data(page, url):

    page_content = page.content()

    try:
        internet_type_btn = page.query_selector_all('.wideScreenFilters__budgetItem__label')

        first_table_data = extract_internet_table_data(page_content, url)
        first_btn_text = internet_type_btn[0].inner_text().lower().replace(' ', '_')
        first_table_data = {'product_name': first_btn_text, **first_table_data}

        internet_type_btn[1].click()

        page_content = page.content()

        second_table_data = extract_internet_table_data(page_content, url)
        second_btn_text = internet_type_btn[1].inner_text().lower().replace(' ', '_')
        second_table_data = {'product_name': second_btn_text, **second_table_data}

        internet_data = []
        internet_data.append(first_table_data)
        internet_data.append(second_table_data)

        return internet_data

    except Exception as e:
        error_message = f"Error extracting internet data: {str(e)}"
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def get_mobile_prepaid_data(browser, url):

    page = goto_page(browser, url)
    time.sleep(5)
    logging.info(f"Extracting mobile prepaid data from: {url}")
    mobile_prepaid_data = extract_prepaid_data(page, url)
    page.close()

    return mobile_prepaid_data


def get_mobile_subscription_data(browser, url):

    page = goto_page(browser, url)
    time.sleep(5)
    logging.info(f"Extracting mobile subscription from: {url}")
    page_content = page.content()
    mobile_subscription_data = extract_subscription_data(page_content, url)
    page.close()

    return mobile_subscription_data


def get_internet_subscription_data(browser, url):

    page = goto_page(browser, url)
    time.sleep(5)
    logging.info(f"Extracting internet subscription data from: {url}")
    internet_subscription_data = extract_internet_data(page, url)
    page.close()

    return internet_subscription_data


def get_products(browser, url):

    try:
        prepaid_data = get_mobile_prepaid_data(browser, url['mobile_prepaid'])
        mobile_subscription_data = get_mobile_subscription_data(browser, url['mobile_subscription'])
        internet_subscription_data = get_internet_subscription_data(browser, url['internet_subscription'])

        product_list = []
        product_list.extend(prepaid_data)
        product_list.extend(mobile_subscription_data)
        product_list.extend(internet_subscription_data)

        # Create an instance of the Products pydantic class
        products_instance = Products(products=product_list)

        # Convert the products_instance to a dictionary
        products_dict = products_instance.model_dump()

        return products_dict

    except ValidationError as validation_error:
        error_message = f"Validation error: {validation_error}"
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def extract_combo_advantage(url):
    try:
        page_content = requests.get(url).text
        soup = BeautifulSoup(page_content, "html.parser")
        combo_text = soup.select_one('.monthlyPrice__discountMessage').get_text()
        match = re.search(r'\d+', combo_text)
        combo_advantage = int(match.group())

        return combo_advantage

    except Exception as e:
        error_message = f'Error extracting combo: {str(e)}'
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def generate_packs(products_list, combo_advantage, url):
    """
    Generate packs based on mobile + internet products combinations
    """
    logging.info('Generating packs')
    try:
        packs_list = []
        date = time.strftime("%Y-%m-%d")

        mobile_products = [product for product in products_list if 'mobile' in product['product_name']]
        internet_products = [product for product in products_list if 'internet' in product['product_name']]

        for internet_product in internet_products:
            for mobile_product in mobile_products:
                price = float(mobile_product['price']) + float(internet_product['price']) - combo_advantage

                pack_name = f"{mobile_product['product_name']}_{internet_product['product_name']}"
                competitor_name = internet_product['competitor_name']

                # mobile_product_name = mobile_product['product_name']
                # internet_product_name = internet_product['product_name']

                packs_list.append(
                    {
                        'competitor_name': competitor_name,
                        'pack_name': pack_name,
                        'pack_url': url,
                        'pack_description': None,
                        'price': price,
                        'scraped_at': date,
                        # 'mobile_product_name': mobile_product_name,
                        # 'internet_product_name': internet_product_name
                    })

        packs_dict = {'packs': packs_list}

        return packs_dict

    except Exception as e:
        error_message = f'Error generating packs: {str(e)}'
        logging.error(error_message)
        traceback.print_exc()
        raise AirflowException(error_message)


def mobileviking_scraper():

    with sync_playwright() as pw:
        start_time = time.strftime("%Y-%m-%d %H:%M:%S")
        start_time_seconds = time.time()
        error_details = 'no error'

        log_file_name = 'test.log'
        log_file_path = f"logs/{log_file_name}"

        log_format = '%(asctime)s [%(levelname)s] - %(message)s'
        logging.basicConfig(filename=log_file_path, level=logging.INFO, format=log_format)
        logging.info(f"=========== mobileviking_scraper start: {start_time} ===========")

        browser = pw.chromium.launch(headless=True, slow_mo=50)

        try:
            # TODO: add typing
            product_dict = get_products(browser, URL)
            save_to_json(product_dict, "mobileviking", 'products')

            combo_advantage = extract_combo_advantage(URL['combo'])
            packs_dict = generate_packs(product_dict['products'], combo_advantage, URL['combo'])
            save_to_json(packs_dict, "mobileviking", 'packs')

        except Exception as e:
            error_message = f"Error in mobileviking_scraper function: {str(e)}"
            logging.error(error_message)
            error_details = error_message
            traceback.print_exc()
            # stack_trace = traceback.format_exc()
            raise AirflowException(error_message)
        finally:
            browser.close()

            end_time_seconds = time.time()
            execution_time_message = "mobileviking_scraper execution time: {:.3f}s".format(end_time_seconds - start_time_seconds)
            logging.info(execution_time_message)

            end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"=========== mobileviking_scraper end: {end_time} ===========")

            save_scraping_log(error_details, 'mobileviking')
