from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
import time
import csv
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_scraper.log'),
        logging.StreamHandler()
    ]
)

class AmazonScraper:
    def __init__(self):
        self.driver = None
        self.product_data = []
        self.logger = logging.getLogger(__name__)
        
    def start_browser(self):
        """Initialize the browser with stealth settings"""
        if self.driver is None:
            try:
                options = Options()
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--start-maximized')
                options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                self.driver = webdriver.Chrome(options=options)
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.logger.info("Browser started successfully")
            except Exception as e:
                self.logger.error(f"Failed to start browser: {str(e)}")
                raise

    def safe_get_text(self, xpath, wait_time=5):
        """Safely extract text from an element using xpath"""
        try:
            element = WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return element.text
        except (NoSuchElementException, TimeoutException):
            return "N/A"
            
    def verify_page_navigation(self):
        """Verify if page navigation is possible and count total pages"""
        try:
            self.logger.info("Starting page navigation verification...")
            page_count = 1
            page_links = []
            
            while True:
                # Wait for pagination section to be visible
                pagination = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-pagination-container"))
                )
                
                # Log current page info
                current_url = self.driver.current_url
                self.logger.info(f"Verifying page {page_count} at URL: {current_url}")
                page_links.append(current_url)
                
                # Check for next button
                try:
                    next_button = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a.s-pagination-next"))
                    )
                    
                    # Check if next button is disabled
                    if "s-pagination-disabled" in next_button.get_attribute("class"):
                        self.logger.info(f"Reached last page. Total pages found: {page_count}")
                        break
                    
                    # Scroll next button into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    time.sleep(1)
                    
                    # Try to click the next button
                    try:
                        next_button.click()
                        self.logger.info(f"Successfully navigated to page {page_count + 1}")
                        page_count += 1
                        time.sleep(2)
                    except ElementClickInterceptedException:
                        self.logger.error("Next button was intercepted by another element")
                        break
                        
                except TimeoutException:
                    self.logger.info("No next button found. Reached last page.")
                    break
                    
            return page_links
            
        except Exception as e:
            self.logger.error(f"Error during page navigation verification: {str(e)}")
            return []

    def navigate_to_search_and_sort(self, search_term):
        """Navigate to Amazon, search for term, and sort by Best Sellers"""
        try:
            self.logger.info(f"Navigating to Amazon and searching for: {search_term}")
            self.driver.get('https://www.amazon.com')
            time.sleep(2)
            
            # Search for the term
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
            )
            search_box.clear()
            search_box.send_keys(search_term)
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
            
            self.logger.info("Sorting by Best Sellers...")
            # Sort by Best Sellers
            sort_dropdown = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "a-dropdown-container"))
            )
            sort_dropdown.click()
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "a-dropdown-link"))
            )
            
            dropdown_options = self.driver.find_elements(By.CLASS_NAME, "a-dropdown-link")
            for option in dropdown_options:
                if "Best Sellers" in option.text:
                    option.click()
                    self.logger.info("Successfully sorted by Best Sellers")
                    break
            
            time.sleep(3)
            return True
            
        except Exception as e:
            self.logger.error(f"Error in navigation and sorting: {str(e)}")
            return False
            
    def process_page(self):
        """Process all products on the current page"""
        try:
            # Create a list to store products from this page specifically
            current_page_data = []
            
            # Get all product links on the current page
            product_links = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//a[@class='a-link-normal s-underline-text s-underline-link-text s-link-style a-text-normal']")
                )
            )
            
            # Store all product URLs
            product_urls = [link.get_attribute('href') for link in product_links]
            self.logger.info(f"Found {len(product_urls)} products on current page")
            
            # Visit each product page and extract information
            for url in product_urls:
                try:
                    self.driver.get(url)
                    product_info = self.extract_product_info()
                    if product_info:
                        current_page_data.append(product_info)
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"Error processing product URL {url}: {str(e)}")
                    continue

            # Add the current page's data to the main product_data list
            self.product_data.extend(current_page_data)
            
            # Return the current page's data for immediate saving
            return current_page_data

        except Exception as e:
            self.logger.error(f"Error processing page: {str(e)}")
            return []

    def extract_product_info(self):
        """Extract information from the current product page"""
        time.sleep(2)  # Wait for page to load completely
        
        try:
            # Extract all required information using specific XPath selectors
            product_info = {
                # Product name from the title
                'name': self.safe_get_text("//span[@id='productTitle']").strip(),
                
                # Rating out of 5 stars
            'rating': self.safe_get_text("/html/body/div[1]/div/div/div[4]/div[4]/div[3]/div/span[1]/span/span[1]/a/span"),
            
                # Total number of reviews
                'total_reviews': self.safe_get_text("//span[@id='acrCustomerReviewText']"),
                
                # Price (whole number part)
                'price': self.safe_get_text("//span[contains(@class, 'a-price')]//span[contains(@class, 'a-price-whole')]"),
                
                # Number of people who bought in past month
                'buyers': self.safe_get_text("//span[contains(text(), 'bought in past month')]")
            }
            
            # Clean up the extracted data
            if product_info['rating']:
                # Convert "4.5 out of 5 stars" to just "4.5"
                product_info['rating'] = product_info['rating'].split(' out')[0]
            
            if product_info['total_reviews']:
                # Convert "1,234 ratings" to just "1234"
                product_info['total_reviews'] = product_info['total_reviews'].split(' ')[0].replace(',', '')
            
            if product_info['buyers']:
                # Clean up buyers data (e.g., "10K+ bought..." to "10000")
                product_info['buyers'] = product_info['buyers'].split(' bought')[0].replace(',', '')
                if 'K+' in product_info['buyers']:
                    product_info['buyers'] = product_info['buyers'].replace('K+', '000')
            
            # Log what we found
            self.logger.info(f"Extracted data: Name: {product_info['name'][:50]}... | " + 
                           f"Rating: {product_info['rating']} | " +
                           f"Reviews: {product_info['total_reviews']} | " +
                           f"Price: ${product_info['price']} | " +
                           f"Buyers: {product_info['buyers']}")
            
            return product_info
            
        except Exception as e:
            self.logger.error(f"Error extracting product info: {str(e)}")
            return None

    def scrape_products(self, search_term):
        """Main method to handle the scraping process"""
        try:
            # Start browser
            self.start_browser()
            
            # Navigate and sort
            if not self.navigate_to_search_and_sort(search_term):
                self.logger.error("Failed to navigate and sort. Exiting...")
                return
            
            # First verify all pages are accessible
            self.logger.info("Verifying page navigation...")
            page_links = self.verify_page_navigation()
            
            if not page_links:
                self.logger.error("No pages found or navigation verification failed")
                return
                
            self.logger.info(f"Found {len(page_links)} pages to scrape")
            
            # Now navigate to each verified page and scrape
            for i, page_url in enumerate(page_links, 1):
                self.logger.info(f"Scraping page {i} of {len(page_links)}")
                try:
                    self.driver.get(page_url)
                    time.sleep(2)
                    # Process page and get current page data
                    current_page_data = self.process_page()
                    
                    # Save current page data immediately
                    self.save_page_data(current_page_data, i)
                    
                    # Also update the combined file
                    self.save_combined_data()
                    
                    self.logger.info(f"Completed scraping and saving page {i}")
                    
                except Exception as e:
                    self.logger.error(f"Error scraping page {i}: {str(e)}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Fatal error in scraping process: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()

    def save_page_data(self, page_data, page_number):
        """Save data for a specific page"""
        if not page_data:
            self.logger.warning(f"No data to save for page {page_number}")
            return
            
        fieldnames = ['name', 'rating', 'total_reviews', 'price', 'buyers']
        page_filename = f'amazon_products_page_{page_number}.csv'
        
        try:
            with open(page_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(page_data)
            self.logger.info(f"Saved {len(page_data)} products to {page_filename}")
        except Exception as e:
            self.logger.error(f"Error saving page data: {str(e)}")

    def save_combined_data(self):
        """Save all collected data to a combined file"""
        if not self.product_data:
            self.logger.warning("No combined data to save")
            return
            
        fieldnames = ['name', 'rating', 'total_reviews', 'price', 'buyers']
        combined_filename = 'amazon_products_all.csv'
        
        try:
            with open(combined_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.product_data)
            self.logger.info(f"Saved combined data ({len(self.product_data)} products) to {combined_filename}")
        except Exception as e:
            self.logger.error(f"Error saving combined data: {str(e)}")

def main():
    scraper = AmazonScraper()
    search_term = input("Enter search term: ")
    scraper.scrape_products(search_term)

if __name__ == "__main__":
    main()