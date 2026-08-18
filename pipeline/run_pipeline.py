import pandas as pd
import os

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {{len(df)}}')
    
    df = df.drop_duplicates(subset=['transaction_id'])
    df = df.dropna(subset=['price'])
    
    # Flag rows with missing customer_email
    null_email_df = df[df['customer_email'].isna()].copy()
    if not null_email_df.empty:
        null_email_df['flag_reason'] = 'baseline drift: unexpected nulls in customer_email'
        flag_path = 'data/flagged_orders.csv'
        # Write header only if the file does not already exist
        write_header = not os.path.exists(flag_path)
        null_email_df.to_csv(flag_path, index=False, mode='a', header=write_header)
        # Exclude flagged rows from the main DataFrame
        df = df[~df['customer_email'].isna()]
    
    print(f'Rows after cleaning: {{len(df)}}')
    
    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()
