import os
import tempfile
import requests
from typing import Dict, Any, List
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime

def download_xbrl(url: str, auth) -> str:
    """Download iXBRL file to a temporary location"""
    print(f"\nDownloading iXBRL from: {url}")
    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Create temp file with .html extension as iXBRL files are HTML
        fd, path = tempfile.mkstemp(suffix='.html')
        with os.fdopen(fd, 'wb') as tmp:
            tmp.write(response.content)
        
        file_size = os.path.getsize(path)
        print(f"Downloaded iXBRL file ({file_size} bytes) to {path}")
        
        # Quick validation of content
        with open(path, 'r', encoding='utf-8') as f:
            first_line = f.readline().lower()
            if 'html' not in first_line and '<?xml' not in first_line:
                print("Warning: Downloaded file might not be valid XHTML/iXBRL")
                print(f"File starts with: {first_line[:100]}")
        
        return path
    except Exception as e:
        print(f"Error downloading iXBRL: {str(e)}")
        return None

def extract_financial_facts(html_content: str) -> List[Dict[str, Any]]:
    """Extract financial facts from iXBRL HTML content"""
    print("\nParsing iXBRL content...")
    facts = []
    
    try:
        # Try different parsers in case one fails
        for parser in ['lxml', 'html.parser', 'xml']:
            try:
                soup = BeautifulSoup(html_content, parser)
                break
            except Exception as e:
                print(f"Parser {parser} failed: {str(e)}")
                continue

        # Print the full HTML structure for debugging
        print("\nDocument structure:")
        print(soup.prettify()[:1000])  # First 1000 chars of pretty-printed HTML
        
        # Look for all possible tags that might contain financial data
        financial_tags = [
            # Standard iXBRL tags
            'ix:nonfraction', 'ix:nonFraction', 'ix:nonfraction', 
            'ix:nonfracion', 'ixnonfraction', 'ixnonFraction',
            # Additional possible tags
            'ix:numerator', 'ix:denominator', 'ix:fraction',
            'itag:nonfraction', 'itag:nonFraction',
            # Common namespace variations
            'ixt:nonfraction', 'ixt:nonFraction',
            # Generic numeric containers
            '[contextref]', '[unitref]'
        ]

        # First, try to find any element with contextref attribute (characteristic of iXBRL)
        elements_with_context = soup.find_all(attrs={'contextref': True})
        print(f"\nFound {len(elements_with_context)} elements with contextref attribute")
        
        # Also look for elements with specific namespaces
        for tag in financial_tags:
            if '[' in tag:  # Handle attribute-based search
                attr_name = tag.strip('[]')
                elements = soup.find_all(attrs={attr_name: True})
            else:
                elements = soup.find_all(tag)
            if elements:
                print(f"Found {len(elements)} {tag} elements")
                elements_with_context.extend(elements)

        # Remove duplicates while preserving order
        seen = set()
        elements_with_context = [x for x in elements_with_context if not (x in seen or seen.add(x))]
        
        print(f"\nTotal unique financial elements found: {len(elements_with_context)}")
        
        # Process each element that might contain financial data
        for element in elements_with_context:
            try:
                # Get all attributes of the element for debugging
                print("\nElement found:")
                print(f"Tag: {element.name}")
                print(f"Attributes: {element.attrs}")
                print(f"Content: {element.get_text().strip()}")
                
                # Try to extract name/concept from various possible attributes
                name = (
                    element.get('name') or 
                    element.get('concept') or 
                    element.get('contextref', '').split('_')[-1]
                )
                
                context_ref = element.get('contextref', '')
                unit_ref = element.get('unitref', '')
                value = element.get_text().strip()
                
                # Try to convert value to number
                try:
                    # Handle different number formats
                    value = value.replace(',', '')
                    if '(' in value:  # Handle parentheses for negative numbers
                        value = value.replace('(', '-').replace(')', '')
                    if '%' in value:  # Handle percentages
                        value = float(value.replace('%', '')) / 100
                    else:
                        value = float(value)
                except ValueError:
                    print(f"Could not convert value: {value}")
                    continue
                
                # Look for context in the entire document
                context = soup.find(['xbrli:context', 'context', 'ix:context', 'xbrli:period', 'period'], 
                                 id=context_ref)
                period = None
                if context:
                    # Try to find period information anywhere in the context
                    instant = context.find(['xbrli:instant', 'instant'])
                    if instant:
                        period = instant.get_text().strip()
                    else:
                        start = context.find(['xbrli:startdate', 'startdate'])
                        end = context.find(['xbrli:enddate', 'enddate'])
                        if start and end:
                            period = f"{start.get_text().strip()}/{end.get_text().strip()}"
                
                # Look for unit information in the entire document
                unit = soup.find(['xbrli:unit', 'unit', 'ix:unit'], id=unit_ref)
                unit_measure = None
                if unit:
                    measure = unit.find(['xbrli:measure', 'measure'])
                    if measure:
                        unit_measure = measure.get_text().strip()
                        # Convert common unit codes
                        if unit_measure == 'iso4217:GBP':
                            unit_measure = 'GBP'
                
                fact = {
                    "concept": name,
                    "value": value,
                    "unit": unit_measure,
                    "context": context_ref,
                    "period": period
                }
                print(f"Extracted fact: {fact}")
                facts.append(fact)
                
            except Exception as e:
                print(f"Error processing element: {str(e)}")
                continue
        
        if not facts:
            # If no structured data found, try parsing tables
            print("\nNo structured facts found, analyzing tables...")
            tables = soup.find_all('table')
            for table in tables:
                print(f"\nAnalyzing table: {table.get('class', 'No class')} - {table.get('id', 'No id')}")
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    for cell in cells:
                        text = cell.get_text().strip()
                        if re.search(r'[£$€]?\s*[\d,]+\.?\d*', text):
                            headers = [h.get_text().strip() for h in row.find_all('th')]
                            print(f"Found financial value: {text}")
                            print(f"Row headers: {headers}")
    
    except Exception as e:
        print(f"Error parsing iXBRL: {str(e)}")
        debug_path = os.path.join(tempfile.gettempdir(), f'debug_ixbrl_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Saved problematic content to {debug_path}")
    
    print(f"\nExtracted {len(facts)} facts from document")
    return facts

def get_financial_data(filing_history_item: Dict[str, Any], auth) -> Dict[str, Any]:
    """Extract financial data from a filing history item"""
    print("\nProcessing filing history item:")
    print(json.dumps(filing_history_item, indent=2))
    
    # Get the transaction ID from the links or from the filing data
    transaction_id = (
        filing_history_item.get('links', {}).get('self', '').split('/')[-1] or
        filing_history_item.get('transaction_id')
    )
    
    company_number = filing_history_item.get('links', {}).get('self', '').split('/company/')[-1].split('/')[0]
    
    if transaction_id and company_number:
        # Construct the direct download URL
        xbrl_url = (
            f"https://find-and-update.company-information.service.gov.uk/company/"
            f"{company_number}/filing-history/{transaction_id}/document?format=xhtml&download=1"
        )
        print(f"Constructed direct download URL: {xbrl_url}")
    else:
        print(f"Could not extract transaction_id ({transaction_id}) or company_number ({company_number})")
        return None
    
    print(f"\nTrying to download from: {xbrl_url}")
    temp_path = download_xbrl(xbrl_url, auth)
    
    if temp_path:
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            facts = extract_financial_facts(html_content)
            
            # Clean up
            os.unlink(temp_path)
            
            if facts:
                return {
                    'filing_type': filing_history_item.get('type'),
                    'filing_date': filing_history_item.get('date'),
                    'facts': facts
                }
            else:
                print("No facts extracted from document")
                
        except Exception as e:
            print(f"Error processing XBRL: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    return None