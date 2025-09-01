import pandas as pd
from datetime import date, timedelta
import random

def generate_sample_insurance_data(num_records=50):
    """Generate sample insurance data matching exact schema."""
    
    # Sample data lists
    insured_names = [
        "Ikenna Uzoh Insurance Corp", "Elum Manufacturing Ltd", "Global Trade Solutions",
        "Metro Construction Co", "Tech Innovations Inc", "Green Energy Solutions",
        "Healthcare Associates", "Retail Merchants Group", "Transportation Services",
        "Financial Advisors Ltd", "Real Estate Holdings", "Marina Bay Company"
    ]
    
    data = []
    
    for i in range(num_records):
        # Generate policy number
        policy_number = f"POL{2024}{str(i+1).zfill(6)}"
        
        # Random insured name
        insured_name = random.choice(insured_names)
        
        # Financial amounts
        sum_insured = round(random.uniform(100000, 5000000), 2)
        premium = round(sum_insured * random.uniform(0.001, 0.05), 2)  # 0.1% to 5% of sum insured
        
        # Retention percentages (0-100%)
        own_retention_ppn = round(random.uniform(10, 80), 2)
        treaty_ppn = round(100 - own_retention_ppn, 2)
        
        # Calculate amounts based on percentages
        own_retention_sum_insured = round(sum_insured * (own_retention_ppn / 100), 2)
        treaty_sum_insured = round(sum_insured * (treaty_ppn / 100), 2)
        
        own_retention_premium = round(premium * (own_retention_ppn / 100), 2)
        treaty_premium = round(premium * (treaty_ppn / 100), 2)
        
        # Insurance period (random dates in 2024)
        start_date = date(2024, random.randint(1, 6), random.randint(1, 28))
        end_date = start_date + timedelta(days=365)
        
        # Format period as string (this will be transformed by our pipeline)
        period_of_insurance = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
        
        record = {
            "POLICY NUMBER": policy_number,
            "INSURED NAME": insured_name,
            "SUM INSURED": sum_insured,
            "PREMIUM": premium,
            "OWN RETENTION %": own_retention_ppn,
            "OWN RETENTION SUM INSURED": own_retention_sum_insured,
            "OWN RETENTION PREMIUM": own_retention_premium,
            "TREATY %": treaty_ppn,
            "TREATY SUM INSURED": treaty_sum_insured,
            "TREATY PREMIUM": treaty_premium,
            "PERIOD OF INSURANCE": period_of_insurance
        }
        
        data.append(record)
    
    return data

def create_sample_excel():
    """Create the sample_data.xlsx file."""
    
    # Generate data
    insurance_data = generate_sample_insurance_data(50)
    
    # Create DataFrame
    df = pd.DataFrame(insurance_data)
    
    # Create Excel file with proper formatting
    with pd.ExcelWriter('sample_data.xlsx', engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Insurance Policies', index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Insurance Policies']
        
        # Format headers
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Format currency columns
        currency_format = workbook.add_format({'num_format': '#,##0.00'})
        percentage_format = workbook.add_format({'num_format': '0.00%'})
        
        # Apply formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
            # Set column widths
            if 'NAME' in value:
                worksheet.set_column(col_num, col_num, 25)
            elif 'PERIOD' in value:
                worksheet.set_column(col_num, col_num, 20)
            elif '%' in value:
                worksheet.set_column(col_num, col_num, 12)
            else:
                worksheet.set_column(col_num, col_num, 18)
    
    print("sample_data.xlsx created successfully!")
    print(f"Generated {len(insurance_data)} insurance policy records")
    
    # Display sample of the data
    print("\n Sample records:")
    sample_df = pd.DataFrame(insurance_data[:3])
    for col in ['SUM INSURED', 'PREMIUM', 'OWN RETENTION SUM INSURED', 'TREATY SUM INSURED']:
        if col in sample_df.columns:
            sample_df[col] = sample_df[col].apply(lambda x: f"₦{x:,.2f}")  #in naira
    
    print(sample_df.to_string(index=False))

if __name__ == "__main__":
    create_sample_excel()