import requests
import pandas as pd
import time
import os
import argparse
import duckdb
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
from datetime import datetime
from dotenv import load_dotenv
from get_xbrl_data import get_financial_data

class CompaniesHouseData:
    """
    A class to interact with the Companies House API.
    """
    def __init__(self, api_key: str, rate_limit_pause: float = 0.5):
        self.api_key = api_key
        self.rate_limit_pause = rate_limit_pause
        self.current_date = datetime.now()
        
        self.auth = requests.auth.HTTPBasicAuth(api_key, '')
        self.headers = {'Accept': 'application/json'}
        
        self.base_urls = [
            "https://api.companieshouse.gov.uk",
            "https://api.company-information.service.gov.uk"
        ]
        
        self.base_url = self.test_connection()
        if not self.base_url:
            raise ValueError("Could not connect to Companies House API. Please check your API key.")

    def test_connection(self) -> str:
        """
        Tests the connection to the Companies House API.

        Returns:
            - The base URL of the connected API or an empty string if the connection failed
        """
        for url in self.base_urls:
            try:
                print(f"\nTesting API endpoint: {url}")
                response = requests.get(
                    f"{url}/search/companies",
                    auth=self.auth,
                    headers=self.headers,
                    params={'q': 'A'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"Successfully connected to {url}")
                    return url
                else:
                    print(f"Failed to connect to {url}: {response.status_code}")
            except Exception as e:
                print(f"Error testing {url}: {str(e)}")
        
        return ""

    def make_request(self, endpoint: str, params: Dict[str, Any], silent: bool = False) -> Dict[str, Any]:
        """
        Makes a GET request to the Companies House API.

        Input:
            - endpoint: The API endpoint to call
            - params: The query parameters for the request
            - silent: If True, suppress error messages

        Output:
            - The JSON response from the API or an error message
        """
        time.sleep(self.rate_limit_pause)
        response = requests.get(
            f"{self.base_url}/{endpoint}",
            auth=self.auth,
            params=params
        )
        if response.status_code == 200:
            return response.json()
        else:
            if not silent:
                print(f"Error {response.status_code} for {endpoint}: {response.text}")
            return {}

    def find_earliest_company_date(self, sic_code: str) -> datetime:
        """
        Binary search to find the earliest company incorporation date.
        Uses a more precise binary search that narrows down to the exact year.

        Input:
            - sic_code: The SIC code to filter companies

        Output:
            - The earliest incorporation date as a datetime object
        """
        print(f"\nSearching for earliest company date for SIC code {sic_code}...")
        
        # First, do a coarse search by years to find the right decade
        start_year = 1800
        end_year = self.current_date.year
        earliest_year = end_year
        
        while start_year < end_year:
            mid_year = (start_year + end_year) // 2
            mid_date = datetime(mid_year, 1, 1)
            
            params = {
                'company_status': "active",
                'size': 1,
                'start_index': 0,
                'sic_codes': sic_code,
                'company_type': "ltd",
                'incorporated_to': mid_date.strftime("%Y-%m-%d")
            }
            
            results = self.make_request('advanced-search/companies', params, silent=True)
            total_hits = results.get('hits', 0)
            
            if total_hits > 0:
                end_year = mid_year
                earliest_year = mid_year
            else:
                start_year = mid_year + 1
        
        # Now do a more precise search within that year
        earliest_date = datetime(earliest_year, 12, 31)
        start_date = datetime(earliest_year, 1, 1)
        end_date = datetime(earliest_year, 12, 31)
        
        while (end_date - start_date).days > 5:  # Get precise to within a week
            mid_date = start_date + (end_date - start_date) / 2
            
            params = {
                'company_status': "active",
                'size': 1,
                'start_index': 0,
                'sic_codes': sic_code,
                'company_type': "ltd",
                'incorporated_to': mid_date.strftime("%Y-%m-%d")
            }
            
            results = self.make_request('advanced-search/companies', params, silent=True)
            total_hits = results.get('hits', 0)
            
            if total_hits > 0:
                end_date = mid_date
                earliest_date = mid_date
            else:
                start_date = mid_date
        
        print(f"Earliest company for SIC {sic_code} found around: {earliest_date.strftime('%Y-%m-%d')}")
        return earliest_date
    
    def fetch_companies_batch(self, endpoint: str, params: Dict[str, Any]) -> Set[str]:
        """
        Fetches companies from a paginated API endpoint for a given parameter set.

        Input:
            - endpoint: The API endpoint to fetch companies from
            - params: The parameters to include in the request

        Output:
            - Set of unique company numbers
        """
        companies = set()
        total_hits = params.get("hits", 0)

        while params['start_index'] < total_hits:
            print(f"Fetching companies at index {params['start_index']}")

            time.sleep(self.rate_limit_pause)
            results = self.make_request(endpoint, params)

            if not results or 'items' not in results:
                print(f"No results at index {params['start_index']}")
                break

            for item in results['items']:
                if (item.get('company_status') == 'active' and
                    item.get('company_type') == 'ltd' and
                    'company_number' in item):
                    companies.add(item['company_number'])

            print(f"Collected {len(companies)} companies")
            params['start_index'] += params['size']

        return companies
    
    def fetch_with_time_windows(self, sic_code: str, earliest_date: datetime) -> Set[str]:
        """
        Handles cases where more than 5000 results exist by splitting requests into time windows.
        Uses an adaptive window size strategy to efficiently collect all companies.

        Input:
            - sic_code: The SIC code to filter companies
            - earliest_date: The earliest incorporation date to consider

        Output:
            - Set of unique company numbers
        """
        companies = set()
        window_end = self.current_date
        window_start = window_end - timedelta(days=365)  # Start with 1-year window
        min_window_days = 30  # Minimum window size of 1 month
        max_window_days = 1825  # Maximum window size of 5 years

        while window_end > earliest_date:
            effective_start = max(window_start, earliest_date)
            if effective_start >= window_end:
                break  # We've reached or passed the earliest date

            params = {
                'company_status': "active",
                'size': 5000,
                'start_index': 0,
                'sic_codes': sic_code,
                'company_type': "ltd",
                'incorporated_from': effective_start.strftime("%Y-%m-%d"),
                'incorporated_to': window_end.strftime("%Y-%m-%d")
            }

            initial = self.make_request('advanced-search/companies', params, silent=True)
            if not initial:
                if effective_start == window_start:
                    break
                print(f"Failed window {params['incorporated_from']} to {params['incorporated_to']}")
                # On failure, try a larger window to skip empty periods faster
                window_size = (window_end - window_start).days
                new_size = min(window_size * 3, max_window_days)  # Triple the window size up to max
                window_start = window_start - timedelta(days=new_size)
                window_start = max(window_start, earliest_date)
                continue

            total_hits = initial.get('hits', 0)
            window_size = (window_end - effective_start).days
            print(f"Window {params['incorporated_from']} to {params['incorporated_to']} ({window_size} days) → {total_hits} companies")

            if total_hits > 5000:
                # Too many results, reduce window size
                print(f"Too many results ({total_hits}), reducing window size...")
                if window_size <= min_window_days:
                    # If window is already at minimum, force process it in batches
                    print("Warning: Minimum window size reached, processing in batches...")
                    companies |= self.fetch_companies_batch('advanced-search/companies', {**params, 'hits': total_hits})
                    window_end = window_start
                    window_start = window_end - timedelta(days=365)  # Reset to 1-year window
                else:
                    # Halve the window size
                    window_start = window_end - timedelta(days=max(min_window_days, window_size // 2))
                continue

            # Window size is good, process the results
            companies |= self.fetch_companies_batch('advanced-search/companies', {**params, 'hits': total_hits})

            # Move window backward and adjust size based on results
            window_end = window_start
            current_window = window_size

            # Adjust window size based on number of results
            if total_hits == 0:  # No companies found
                # Triple the window size to cover more ground faster
                new_window = min(current_window * 3, max_window_days)
            elif total_hits < 100:  # Very few companies
                # Double the window size
                new_window = min(current_window * 2, max_window_days)
            elif total_hits < 2000:  # Few companies
                # Increase window by 50%
                new_window = min(int(current_window * 1.5), max_window_days)
            elif total_hits > 4000:  # Getting close to limit
                # Reduce window size
                new_window = max(min_window_days, current_window // 2)
            else:
                # Keep current window size
                new_window = current_window

            window_start = window_end - timedelta(days=new_window)

        return companies

    def save_company_numbers(self, company_numbers: List[str], output_dir: str = "company_numbers"):
        """Save company numbers to Parquet files in chunks"""
        os.makedirs(output_dir, exist_ok=True)
        chunk_size = 20000  
        for i in range(0, len(company_numbers), chunk_size):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            df_chunk = pd.DataFrame({"company_number": company_numbers[i:i+chunk_size]})
            file_path = os.path.join(output_dir, f"chunk_{i//chunk_size}-{timestamp}.parquet")
            df_chunk.to_parquet(file_path, index=False)

        print(f"Guardados {len(company_numbers)} company_numbers en {output_dir}")

    def get_companies(self, sic_codes: List[str]) -> List[str]:
        """
        Fetches company numbers for active LTD companies
        within specified SIC codes, using pagination and
        time-windowing if necessary.

        Input:
            - sic_codes: List of SIC codes to filter companies

        Output:
            - List of unique company numbers
        """

        all_companies = set()
        print("Starting advanced search for sector companies…")

        for sic_code in sic_codes:
            print(f"Processing SIC code: {sic_code}")

            params = {
                'company_status': "active",
                'size': 5000,
                'start_index': 0,
                'sic_codes': sic_code,
                'company_type': "ltd",
                'incorporated_from': "1900-01-01",
                'incorporated_to': self.current_date.strftime("%Y-%m-%d")
            }

            initial = self.make_request('advanced-search/companies', params, silent=False)
            if not initial:
                print(f"Failed to get initial results for SIC {sic_code}")
                continue

            total_hits = initial.get('hits', 0)
            print(f"Found {total_hits} companies for SIC {sic_code}")

            if total_hits <= 5000:
                all_companies |= self.fetch_companies_batch('advanced-search/companies', {**params, 'hits': total_hits})
            else:
                earliest_date = self.find_earliest_company_date(sic_code)
                all_companies |= self.fetch_with_time_windows(sic_code, earliest_date)

        # Deduplicate (already a set, but we log stats for clarity)
        company_list = sorted(all_companies)
        print(f"Final unique companies: {len(company_list)}")

        self.save_company_numbers(company_list)
        return company_list

    def get_company_details(self, company_number: str) -> Dict[str, Any]:
        """Get comprehensive company information including iXBRL financial data"""
        
        print(f"\nProcessing company {company_number}")
        
        # Get basic info first
        basic_info = self.make_request(f'company/{company_number}', {})
        if not basic_info:
            print(f"Could not get basic information for company {company_number}")
            return None
        print(f"Successfully got basic info for {company_number}: {basic_info.get('company_name', 'Unknown')}")
        
        # Initialize details dictionary with all API endpoints
        details = {
            'company_number': company_number,
            'basic_info': basic_info,
            'filing_history': self.make_request(f'company/{company_number}/filing-history', {}, silent=True),
            'officers': self.make_request(f'company/{company_number}/officers', {}, silent=True),
            'persons_significant_control': self.make_request(f'company/{company_number}/persons-with-significant-control', {}, silent=True),
            'charges': self.make_request(f'company/{company_number}/charges', {}, silent=True),
            'insolvency': self.make_request(f'company/{company_number}/insolvency', {}, silent=True),
            'registers': self.make_request(f'company/{company_number}/registers', {}, silent=True),
            'uk_establishments': self.make_request(f'company/{company_number}/uk-establishments', {}, silent=True),
            'financials': None,
            'fetch_timestamp': datetime.now().isoformat()
        }
        print(details.get('filing_history',''))
        
        # Process accounts and financial data if available
        if 'accounts' in basic_info:
            print(f"Company has accounts information. Last made up to: {basic_info['accounts'].get('last_accounts', {}).get('made_up_to', 'Unknown')}")
            
            filing_history = details['filing_history'].get('items', [])
            if not filing_history:
                print(f"No filing history found for company {company_number}")
                return details
                
            print(f"Found {len(filing_history)} total filings")
            
            # Filter for accounts with actual documents
            accounts_filings = [
                filing for filing in filing_history 
                if (filing.get('category') == 'accounts' and
                    filing.get('links', {}).get('document_metadata') is not None)
            ]
            
            # Sort by date (most recent first)
            accounts_filings.sort(
                key=lambda x: x.get('date', ''), 
                reverse=True
            )
            
            if accounts_filings:
                print(f"Found {len(accounts_filings)} accounts filings with documents")
                
                # Extract financial data from iXBRL documents
                financial_data = []
                for filing in accounts_filings:
                    print(f"\nProcessing filing from {filing.get('date')}")
                    print(f"Description: {filing.get('description', 'No description')}")
                    print(f"Category: {filing.get('type', 'Unknown type')}")
                    
                    try:
                        # Add longer timeout for document downloads
                        time.sleep(self.rate_limit_pause * 2)  # Double pause for document requests
                        
                        data = get_financial_data(filing, self.auth)
                        if data and data.get('facts'):
                            print(f"Successfully extracted {len(data['facts'])} financial facts")
                            financial_data.append(data)
                        else:
                            print(f"No financial facts found in filing")
                    except Exception as e:
                        print(f"Error processing filing: {str(e)}")
                        continue
                
                if financial_data:
                    details['financials'] = financial_data
                    print(f"Added financial data from {len(financial_data)} filings")
                    
                    # Print summary of extracted data
                    total_facts = sum(len(data.get('facts', [])) for data in financial_data)
                    print(f"\nFinancial data summary:")
                    print(f"- Total filings processed: {len(financial_data)}")
                    print(f"- Total facts extracted: {total_facts}")
                    
                    # Print sample of facts if available
                    if financial_data and financial_data[0].get('facts'):
                        print("\nSample of extracted facts from most recent filing:")
                        for fact in financial_data[0]['facts'][:5]:
                            print(f"- {fact.get('concept', 'Unknown')}: {fact.get('value', 'No value')} {fact.get('unit', '')}")
                else:
                    print("No financial data could be extracted from any filing")
            else:
                print("No accounts filings with documents found")
        else:
            print(f"No accounts information in basic info for company {company_number}")
        
        return details


def save_company_details(company_details: Dict[str, Any], directory: str = "company_details"):
    """
    Save company details to a parquet file in the specified directory.
    Each company is saved in its own file named by its company number.
    Handles empty dictionaries and null values for proper parquet serialization.
    
    Args:
        company_details (Dict[str, Any]): The company details to save
        directory (str): The directory to save the company details in
    """
    os.makedirs(directory, exist_ok=True)
    company_number = company_details['company_number']
    file_path = os.path.join(directory, f"{company_number}.parquet")
    
    # Clean the data structure
    cleaned_details = {}
    for key, value in company_details.items():
        if isinstance(value, dict):
            if not value:  # Empty dictionary
                cleaned_details[f"{key}_exists"] = False
            else:
                cleaned_details[f"{key}_exists"] = True
                # Flatten first level of dictionary
                for sub_key, sub_value in value.items():
                    cleaned_details[f"{key}_{sub_key}"] = sub_value
        elif value is None:
            cleaned_details[f"{key}_exists"] = False
        else:
            cleaned_details[key] = value
            
    # Convert the cleaned dictionary to a DataFrame with a single row
    df = pd.DataFrame([cleaned_details])
    df.to_parquet(file_path, index=False)

def get_processed_companies(directory: str = "company_details") -> Set[str]:
    """
    Get a set of company numbers that have already been processed by checking
    the existing files in the company_details directory.
    
    Args:
        directory (str): The directory containing the company detail files
        
    Returns:
        Set[str]: Set of company numbers that have already been processed
    """
    if not os.path.exists(directory):
        return set()
        
    # Get all .parquet files in the directory
    processed = {os.path.splitext(f)[0] for f in os.listdir(directory) 
                if f.endswith('.parquet')}
    print(f"Found {len(processed)} previously processed companies")
    return processed

def load_cached_companies(directory: str = "company_numbers") -> List[str]:
    """
    Load all company numbers from parquet files in the cache directory using DuckDB.
    It also handles duplicates, in case cached files contain more than one sic_codes.
    
    Args:
        directory (str): The directory containing the parquet files
        
    Returns:
        List[str]: List of unique company numbers
    """
    if not os.path.exists(directory):
        print(f"Cache directory {directory} does not exist")
        return []
        
    try:
        # Connect to DuckDB
        con = duckdb.connect(':memory:')
        
        # Read all parquet files in the directory
        query = f"""
            SELECT DISTINCT company_number 
            FROM read_parquet('{directory}/*.parquet')
            ORDER BY company_number
        """
        
        # Execute query and fetch results
        result = con.execute(query).fetchall()
        
        # Convert results to list
        company_numbers = [row[0] for row in result]
        
        print(f"Loaded {len(company_numbers)} unique company numbers from cache")
        return company_numbers
        
    except Exception as e:
        print(f"Error loading cached company numbers: {str(e)}")
        return []
    finally:
        con.close()

def load_environment() -> str:
    """
    Load environment variables from .env file and return the API key.
    Searches for .env file in script directory first, then in root directory.
    
    Returns:
        str: The Companies House API key
    
    Raises:
        ValueError: If COMPANIES_HOUSE_API_KEY is not set in .env file
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Try loading from script directory first
    env_file = os.path.join(script_dir, '.env')
    if os.path.exists(env_file):
        print(f"Loading .env from script directory: {env_file}")
        load_dotenv(env_file)
    else:
        # Try loading from root directory
        env_file = os.path.join(root_dir, '.env')
        if os.path.exists(env_file):
            print(f"Loading .env from root directory: {env_file}")
            load_dotenv(env_file)
        else:
            print("No .env file found in script or root directory")
    
    api_key = os.getenv('COMPANIES_HOUSE_API_KEY')
    if not api_key:
        raise ValueError("Please set COMPANIES_HOUSE_API_KEY in .env file")
    
    print(f"API key loaded (first 5 chars): {api_key[:5]}...")
    return api_key

def main():

    ######## ARGUMENT PARSING ########
    parser = argparse.ArgumentParser(description='Fetch company data from Companies House API')
    parser.add_argument('--sic-codes', type=str, default="62020,62030,62090,63110,63120,58290,58210",
                      help='Comma-separated list of SIC codes to search for (default: IT sector codes)')
    parser.add_argument('--use-cache', type=lambda x: str(x).lower() in ['true', '1', 'yes', 'y'],
                      default=False,
                      help='Whether to use cached data (default: False)')
    args = parser.parse_args()
    
    sic_codes = [code.strip() for code in args.sic_codes.split(',')]
    print(f"\nProcessing SIC codes: {', '.join(sic_codes)}")
    print(f"Using cache: {args.use_cache}")

    ######## ENVIRONMENT LOADING ########
    api_key = load_environment()

    ######## DATA FETCHING ########
    data = CompaniesHouseData(api_key)

    company_numbers = []

    if not args.use_cache:
        print("Fetching company numbers.")
        company_numbers = data.get_companies(sic_codes=sic_codes)
        print("Done!")
    else:
        print("Using cached company numbers.")
        company_numbers = load_cached_companies()
        if not company_numbers:
            print("No cached data found or error loading cache. Fetching from API instead.")
            company_numbers = data.get_companies(sic_codes=sic_codes)

    ######### COLLECTING COMPANY INFORMATION #########
    companies_data = []
    successful_companies = 0
    # num_companies = 10
    print("Collecting company information...")

    processed_companies = get_processed_companies()
    remaining_companies = [c for c in company_numbers if c not in processed_companies]
    
    print(f"Total companies: {len(company_numbers)}")
    print(f"Already processed: {len(processed_companies)}")
    print(f"Remaining to process: {len(remaining_companies)}")

    try:
        for company_number in remaining_companies:
            print(f"\nProcessing company {successful_companies + 1}/{len(remaining_companies)}: {company_number}")
            
            company_details = data.get_company_details(company_number)

            if company_details:
                save_company_details(company_details)
                companies_data.append(company_details)
                successful_companies += 1
                print(f"Successfully collected and saved data for {company_number}")
                
                # if successful_companies >= num_companies:
                #     break
            else:
                print(f"Skipping company {company_number} due to missing data")
                
    except KeyboardInterrupt:
        print("\nScript interrupted by user. Progress has been saved.")
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        print("Progress up to this point has been saved.")

if __name__ == "__main__":
    main()
