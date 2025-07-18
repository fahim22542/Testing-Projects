import re
import time
from playwright.sync_api import Playwright, sync_playwright, expect
from typing import List, Dict, Any

# === CONFIGURABLE LIMITS ===
FILTER_LIMITS = {
    "region": None,        # e.g. 2 to limit, None for unlimited
    "area": None,
    "distributor": None,
    "territory": None,
    "point": None
}

def wait_for_loading(page, timeout=15000):
    """Wait for any loading indicators to disappear"""
    try:
        # Wait for common loading indicators
        page.wait_for_selector(".loading", state="hidden", timeout=timeout)
    except:
        pass
    
    try:
        # Wait for any spinner or loading elements
        page.wait_for_selector(".spinner", state="hidden", timeout=timeout)
    except:
        pass
    
    try:
        # Wait for mantine loading overlay
        page.wait_for_selector(".mantine-LoadingOverlay-root", state="hidden", timeout=timeout)
    except:
        pass
    
    # Additional wait for content to stabilize
    time.sleep(2)

def get_dropdown_options(page, dropdown_name: str) -> List[str]:
    """Get all available options from a dropdown"""
    try:
        # Click to open dropdown
        dropdown = page.get_by_role("textbox", name=dropdown_name)
        dropdown.click()
        
        # Wait a bit for dropdown to open
        time.sleep(1)
        
        # Wait for options to be visible with a more specific selector
        page.wait_for_selector('[role="option"]:visible', timeout=10000)
        
        # Get all visible options
        options = page.locator('[role="option"]:visible').all()
        option_texts = []
        
        for option in options:
            try:
                if option.is_visible():
                    text = option.inner_text().strip()
                    if text and text not in option_texts:
                        option_texts.append(text)
            except:
                continue
        
        # Close dropdown by pressing Escape or clicking the dropdown again
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except:
            try:
                # Try clicking the dropdown again to close it
                dropdown.click()
                time.sleep(0.5)
            except:
                # Try clicking somewhere safe
                try:
                    page.locator("body").click()
                    time.sleep(0.5)
                except:
                    pass
        
        return option_texts
    except Exception as e:
        print(f"Error getting options for {dropdown_name}: {e}")
        return []

def select_dropdown_option(page, dropdown_name: str, option_text: str) -> bool:
    """Select a specific option from dropdown"""
    try:
        # Click to open dropdown
        dropdown = page.get_by_role("textbox", name=dropdown_name)
        dropdown.click()
        
        # Wait for options to appear
        time.sleep(1)
        page.wait_for_selector('[role="option"]:visible', timeout=10000)
        
        # Try to find and click the option
        visible_options = page.locator('[role="option"]:visible').all()
        
        for option in visible_options:
            try:
                if option.is_visible():
                    option_inner_text = option.inner_text().strip()
                    if option_text in option_inner_text or option_inner_text in option_text:
                        option.click()
                        time.sleep(1)
                        return True
            except:
                continue
        
        print(f"Could not find option '{option_text}' in {dropdown_name}")
        
        # Close dropdown if option wasn't found
        try:
            page.keyboard.press("Escape")
        except:
            pass
        
        return False
        
    except Exception as e:
        print(f"Error selecting option '{option_text}' from {dropdown_name}: {e}")
        return False

def clear_all_filters(page):
    """Clear all filter selections"""
    try:
        # Close any open dropdowns first
        page.keyboard.press("Escape")
        time.sleep(0.5)
        
        # Click on each filter to reset - try a different approach
        filters = [
            "Filter by Region",
            "Filter by Area", 
            "Filter by Distribution house",
            "Filter by Territory",
            "Filter by Point"
        ]
        
        for filter_name in filters:
            try:
                # Try to find a clear button or use keyboard to clear
                dropdown = page.get_by_role("textbox", name=filter_name)
                dropdown.click()
                time.sleep(0.2)
                
                # Try to clear the field
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                time.sleep(0.2)
                
                # Press escape to close
                page.keyboard.press("Escape")
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Error clearing {filter_name}: {e}")
                continue
                
        # Final escape to ensure all dropdowns are closed
        page.keyboard.press("Escape")
        time.sleep(1)
        
    except Exception as e:
        print(f"Error clearing filters: {e}")

def get_table_data(page) -> List[Dict[str, str]]:
    """Extract data from the current table page"""
    try:
        wait_for_loading(page)
        
        # Wait for table to be present
        page.wait_for_selector('table', timeout=10000)
        
        # Get all rows from the table body
        tbody_rows = page.locator('tbody tr').all()
        
        # If no tbody, try getting all tr elements and skip the first (header)
        if not tbody_rows:
            all_rows = page.locator('tr').all()
            tbody_rows = all_rows[1:] if len(all_rows) > 1 else []
        
        data = []
        
        for row in tbody_rows:
            try:
                cells = row.locator('td').all()
                if len(cells) >= 7:  # Ensure we have enough columns
                    row_data = {
                        'name': cells[0].inner_text().strip(),
                        'code': cells[1].inner_text().strip(),
                        'region': cells[2].inner_text().strip(),
                        'area': cells[3].inner_text().strip(),
                        'distributor': cells[4].inner_text().strip(),
                        'territory': cells[5].inner_text().strip(),
                        'point': cells[6].inner_text().strip()
                    }
                    data.append(row_data)
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
        
        return data
    except Exception as e:
        print(f"Error extracting table data: {e}")
        return []

def get_first_and_last_page_data(page) -> List[Dict[str, str]]:
    """Get data only from first and last pagination pages"""
    all_data = []
    seen_data = set()

    try:
        wait_for_loading(page)

        # === Step 1: First page ===
        first_page_data = get_table_data(page)
        all_data.extend(first_page_data)
        seen_data.update(map(str, first_page_data))
        print(f"✅ Fetched first page — Records: {len(first_page_data)}")

        # === Step 2: Detect all numbered pagination buttons ===
        buttons = page.locator("button.mantine-Pagination-control")
        count = buttons.count()

        last_page_number = None
        last_button_index = None

        for i in range(count):
            btn = buttons.nth(i)
            try:
                if btn.is_visible():
                    text = btn.inner_text().strip()
                    if text.isdigit():
                        if last_page_number is None or int(text) > int(last_page_number):
                            last_page_number = text
                            last_button_index = i
            except:
                continue

        if last_page_number is None:
            print("⚠️ No pagination buttons found — skipping last page.")
            return all_data

        print(f"🔎 Detected last page number: {last_page_number}")

        # === Step 3: Click last page button
        last_button = buttons.nth(last_button_index)
        last_button.scroll_into_view_if_needed()
        page.mouse.wheel(0, -200)  # scroll up to avoid footer
        time.sleep(0.5)
        try:
            last_button.click()
        except:
            print("⚠️ Click blocked, trying JS fallback...")
            element_handle = last_button.element_handle()
            if element_handle:
                page.evaluate("(el) => el.click()", element_handle)
            else:
                print("❌ Could not get element handle for last page button")
        wait_for_loading(page)

        last_page_data = get_table_data(page)
        new_data_str = list(map(str, last_page_data))

        for row_str, row in zip(new_data_str, last_page_data):
            if row_str not in seen_data:
                all_data.append(row)
                seen_data.add(row_str)

        print(f"✅ Fetched last page — Records: {len(last_page_data)}")

    except Exception as e:
        print(f"❌ Error fetching first/last page: {e}")

    return all_data

def get_all_pages_data(page) -> List[Dict[str, str]]:
    """Get data from all pages using hybrid strategy: Next button first, fallback to numbered pagination"""
    all_data = []
    seen_data = set()
    visited_pages = set()  # Track numeric page numbers visited

    try:
        wait_for_loading(page)
        page_data = get_table_data(page)
        all_data.extend(page_data)
        seen_data.update(map(str, page_data))

        while True:
            moved_to_next = False

            # === Try "Next" button first ===
            try:
                next_button = page.locator('button:has-text("Next")')
                if next_button.count() > 0 and next_button.is_visible():
                    is_disabled = next_button.get_attribute("disabled")
                    if not is_disabled:
                        next_button.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        next_button.click()
                        wait_for_loading(page)

                        new_data = get_table_data(page)
                        new_data_str = list(map(str, new_data))

                        if new_data and not all(d in seen_data for d in new_data_str):
                            all_data.extend(new_data)
                            seen_data.update(new_data_str)
                            moved_to_next = True
                            print(f"✅ Clicked 'Next' — Total records: {len(all_data)}")
                            continue
            except Exception as e:
                print(f"⚠️ Error with 'Next' button: {e}")

            # === Fallback: Numbered pagination ===
            try:
                buttons = page.locator('button[role="button"]')
                count = buttons.count()

                for i in range(count):
                    button = buttons.nth(i)
                    try:
                        if button.is_visible():
                            btn_text = button.inner_text().strip()
                            if btn_text.isdigit() and btn_text not in visited_pages:
                                visited_pages.add(btn_text)
                                button.scroll_into_view_if_needed()
                                time.sleep(0.3)
                                button.click()
                                wait_for_loading(page)

                                new_data = get_table_data(page)
                                new_data_str = list(map(str, new_data))

                                if new_data and not all(d in seen_data for d in new_data_str):
                                    all_data.extend(new_data)
                                    seen_data.update(new_data_str)
                                    moved_to_next = True
                                    print(f"✅ Clicked page '{btn_text}' — Total records: {len(all_data)}")
                    except Exception as e:
                        print(f"⚠️ Error clicking page button {i}: {e}")
                        continue
            except Exception as e:
                print(f"⚠️ Error with numbered pagination: {e}")

            if not moved_to_next:
                print("ℹ️ No more pages or data repeated. Ending pagination.")
                break

    except Exception as e:
        print(f"❌ Pagination failure: {e}")

    return all_data

def verify_filters(data: List[Dict[str, str]], filters: Dict[str, str]) -> Dict[str, Any]:
    """Verify that all data matches the selected filters"""
    verification_result = {
        'total_records': len(data),
        'valid_records': 0,
        'invalid_records': [],
        'filter_compliance': {}
    }
    
    filter_mapping = {
        'region': 'region',
        'area': 'area',
        'distributor': 'distributor',
        'territory': 'territory',
        'point': 'point'
    }
    
    for record in data:
        is_valid = True
        record_issues = []
        
        for filter_key, filter_value in filters.items():
            if filter_key in filter_mapping:
                record_field = filter_mapping[filter_key]
                record_value = record.get(record_field, '').strip()
                
                if filter_value.lower() not in record_value.lower():
                    is_valid = False
                    record_issues.append(f"{filter_key}: expected '{filter_value}', got '{record_value}'")
        
        if is_valid:
            verification_result['valid_records'] += 1
        else:
            verification_result['invalid_records'].append({
                'record': record,
                'issues': record_issues
            })
    
    # Calculate compliance percentage for each filter
    for filter_key in filters.keys():
        if filter_key in filter_mapping:
            compliant_count = sum(1 for record in data 
                                if filters[filter_key].lower() in record.get(filter_mapping[filter_key], '').lower())
            verification_result['filter_compliance'][filter_key] = {
                'compliant': compliant_count,
                'total': len(data),
                'percentage': (compliant_count / len(data) * 100) if data else 0
            }
    
    return verification_result

def build_complete_filter_chains(page) -> List[Dict[str, str]]:
    """Build complete filter chains by following the dependency hierarchy"""
    print("Building complete filter chains...")

    complete_chains = []

    # Clear all filters first
    clear_all_filters(page)

    # Get all regions
    print("Getting all regions...")
    regions = get_dropdown_options(page, "Filter by Region")
    if FILTER_LIMITS["region"]:
        regions = regions[:FILTER_LIMITS["region"]]
    print(f"Found {len(regions)} regions")

    if not regions:
        print("No regions found!")
        return complete_chains

    for region in regions:
        print(f"\nProcessing region: {region}")

        clear_all_filters(page)
        if not select_dropdown_option(page, "Filter by Region", region):
            continue
        wait_for_loading(page)

        areas = get_dropdown_options(page, "Filter by Area")
        if FILTER_LIMITS["area"]:
            areas = areas[:FILTER_LIMITS["area"]]
        print(f"Found {len(areas)} areas for region {region}")

        for area in areas:
            print(f"  Processing area: {area}")

            clear_all_filters(page)
            if not select_dropdown_option(page, "Filter by Region", region):
                continue
            wait_for_loading(page)
            if not select_dropdown_option(page, "Filter by Area", area):
                continue
            wait_for_loading(page)

            distributors = get_dropdown_options(page, "Filter by Distribution house")
            if FILTER_LIMITS["distributor"]:
                distributors = distributors[:FILTER_LIMITS["distributor"]]
            print(f"    Found {len(distributors)} distributors for {region}/{area}")

            for distributor in distributors:
                print(f"    Processing distributor: {distributor}")

                clear_all_filters(page)
                if not select_dropdown_option(page, "Filter by Region", region):
                    continue
                wait_for_loading(page)
                if not select_dropdown_option(page, "Filter by Area", area):
                    continue
                wait_for_loading(page)
                if not select_dropdown_option(page, "Filter by Distribution house", distributor):
                    continue
                wait_for_loading(page)

                territories = get_dropdown_options(page, "Filter by Territory")
                if FILTER_LIMITS["territory"]:
                    territories = territories[:FILTER_LIMITS["territory"]]
                print(f"      Found {len(territories)} territories for {region}/{area}/{distributor}")

                for territory in territories:
                    print(f"      Processing territory: {territory}")

                    clear_all_filters(page)
                    if not select_dropdown_option(page, "Filter by Region", region):
                        continue
                    wait_for_loading(page)
                    if not select_dropdown_option(page, "Filter by Area", area):
                        continue
                    wait_for_loading(page)
                    if not select_dropdown_option(page, "Filter by Distribution house", distributor):
                        continue
                    wait_for_loading(page)
                    if not select_dropdown_option(page, "Filter by Territory", territory):
                        continue
                    wait_for_loading(page)

                    points = get_dropdown_options(page, "Filter by Point")
                    if FILTER_LIMITS["point"]:
                        points = points[:FILTER_LIMITS["point"]]
                    print(f"        Found {len(points)} points for {region}/{area}/{distributor}/{territory}")

                    for point in points:
                        print(f"        Adding complete chain with point: {point}")
                        complete_chains.append({
                            'region': region,
                            'area': area,
                            'distributor': distributor,
                            'territory': territory,
                            'point': point
                        })

    print(f"\nBuilt {len(complete_chains)} complete filter chains")
    return complete_chains

def run_comprehensive_test(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    try:
        # Login
        page.goto("https://prismv2.prism360.batbangladesh.dev/")
        page.get_by_role("textbox", name="Email").fill("abir@manush.tech")
        page.get_by_role("textbox", name="Password").fill("Manush@staging123")
        page.get_by_role("button", name="Login").click()
        
        # Navigate to Retailers
        page.get_by_role("button", name="Retailers").click()
        wait_for_loading(page)
        
        # Build complete filter chains
        complete_chains = build_complete_filter_chains(page)
        
        if not complete_chains:
            print("No complete filter chains could be built!")
            return
        
        print(f"\nTesting {len(complete_chains)} complete filter combinations...")
        
        results = []
        
        for i, chain in enumerate(complete_chains, 1):
            print(f"\n--- Test {i}/{len(complete_chains)} ---")
            print(f"Testing complete chain: {chain}")
            
            # Clear all filters
            clear_all_filters(page)
            
            # Apply all filters in sequence
            success = True
            
            # Apply region filter
            success &= select_dropdown_option(page, "Filter by Region", chain["region"])
            if success:
                wait_for_loading(page)
            
            # Apply area filter
            if success:
                success &= select_dropdown_option(page, "Filter by Area", chain["area"])
                if success:
                    wait_for_loading(page)
            
            # Apply distributor filter
            if success:
                success &= select_dropdown_option(page, "Filter by Distribution house", chain["distributor"])
                if success:
                    wait_for_loading(page)
            
            # Apply territory filter
            if success:
                success &= select_dropdown_option(page, "Filter by Territory", chain["territory"])
                if success:
                    wait_for_loading(page)
            
            # Apply point filter
            if success:
                success &= select_dropdown_option(page, "Filter by Point", chain["point"])
                if success:
                    wait_for_loading(page)
            
            if not success:
                print(f"Failed to apply complete filter chain for test {i}")
                continue
            
            # Wait for results to load after all filters are applied
            wait_for_loading(page)
            
            # Get all data from all pages
            all_data = get_first_and_last_page_data(page)
            
            # Verify the results against ALL filters
            verification = verify_filters(all_data, chain)
            
            result = {
                'chain': chain,
                'data_count': len(all_data),
                'verification': verification
            }
            
            results.append(result)
            
            print(f"Found {len(all_data)} records")
            print(f"Valid records: {verification['valid_records']}")
            print(f"Invalid records: {len(verification['invalid_records'])}")
            
            if verification['invalid_records']:
                print("Issues found:")
                for invalid in verification['invalid_records'][:3]:  # Show first 3 issues
                    print(f"  - {invalid['issues']}")
        
        # Print summary
        print(f"\n{'='*60}")
        print("SUMMARY - ALL FILTERS APPLIED")
        print(f"{'='*60}")
        
        total_tests = len(results)
        passed_tests = sum(1 for r in results if len(r['verification']['invalid_records']) == 0)
        
        print(f"Total complete filter combinations tested: {total_tests}")
        print(f"Passed tests: {passed_tests}")
        print(f"Failed tests: {total_tests - passed_tests}")
        print(f"Success rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Show detailed results for failed tests
        failed_tests = [r for r in results if len(r['verification']['invalid_records']) > 0]
        if failed_tests:
            print(f"\nFailed test details:")
            for result in failed_tests:
                print(f"  Chain: {result['chain']}")
                print(f"  Invalid records: {len(result['verification']['invalid_records'])}")
                print(f"  Data count: {result['data_count']}")
        
        # Show some successful tests
        successful_tests = [r for r in results if len(r['verification']['invalid_records']) == 0]
        if successful_tests:
            print(f"\nSuccessful test examples:")
            for result in successful_tests[:3]:  # Show first 3 successful tests
                print(f"  Chain: {result['chain']}")
                print(f"  Records found: {result['data_count']}")
    
    except Exception as e:
        print(f"Error during test execution: {e}")
    
    finally:
        context.close()
        browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run_comprehensive_test(playwright)
