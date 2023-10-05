from playwright.sync_api import sync_playwright
import json
import re
import time
from bs4 import BeautifulSoup



URL = 'https://www.scarlet.be/en/abonnement-gsm.html'

def goto_page(browser, url):
    page = browser.new_page()
    page.goto(url, wait_until='domcontentloaded')
    page.wait_for_selector('#onetrust-accept-btn-handler')
    page.query_selector('#onetrust-accept-btn-handler').click(force=True)
    return page

def extract_mobile_subscription_data(page_content, url):

    mobile_subscription_data = []
    soup = BeautifulSoup(page_content, 'html.parser')
    mobile_subscription_elements = soup.find_all('div', class_="rs-ctable-panel jsrs-resizerContainer")
    #print(mobile_subscription_elements)
    
    for element in mobile_subscription_elements:
        product_name = element.find('h3', class_="rs-ctable-panel-title").get_text().strip()
        price_per_month = element.find('span', class_="rs-unit").get_text()
        elms = element.find_all('li', class_="jsrs-resizerPart")
        mobile_data = elms[0].get_text()
        minutes = elms[2].get_text()
        sms = elms[1].get_text()
        '''for l in elms:
            print(l.get_text())'''
        
            
    
        mobile_subscription_data.append({
            'product_name': f"mobile_subscription_{product_name}",
            'competitor_name': 'scarlet',
            'product_category': 'mobile_subscription',
            'product_url': url,
            'price': price_per_month,
            'data': mobile_data,
            'network': "unknown",
            'minutes': minutes,
            'price_per_minute': '',
            'sms': sms,
            'upload_speed': '',
            'download_speed': '',
            'line_type': ''
                })
       # print(element.find('li', class_="jsrs-resizerPart").get_text())
    return mobile_subscription_data
  
def get_mobile_subscription_data(browser, url):
    page = goto_page(browser, url)
    time.sleep(5)
    page_content = page.content()

    mobile_subscription_data = extract_mobile_subscription_data(page_content, url)
    page.close()
    return mobile_subscription_data

def get_products(browser, url):
    start = time.time()
    mobile_subscription_data = get_mobile_subscription_data(browser, url)
    product_list =[]
    product_list.extend(mobile_subscription_data)

    product_dict = {'products': product_list}
    end = time.time()
    print("Time taken to scrape products: {:.3f}s".format(end - start))
    return product_dict


def main():    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try: 
            product_dict = get_products(browser, URL)
            print(product_dict)
        except Exception as e:
            print(f"Error in main function:{str(e)}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()



