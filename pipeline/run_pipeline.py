import pandas as pd
import os

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {len(df)}')
    
    # Flag rows with null customer_email
    null_email_mask = df['customer_email'].isna()
    if null_email_mask.any():
        flagged = df[null_email_mask].copy()
        flagged['flag_reason'] = 'baseline drift: unexpected nulls in customer_email'
        flagged_path = 'data/flagged_orders.csv'
        if os.path.exists(flagged_path):
            flagged.to_csv(flagged_path, mode='a', index=False, header=False)
        else:
            flagged.to_csv(flagged_path, index=False)
        # Exclude flagged rows from further processing
        df = df[~null_email_mask]
    
    df = df.drop_duplicates(subset=['transaction_id'])
    df = df.dropna(subset=['price'])
    
    print(f'Rows after cleaning: {len(df)}')
    
    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()
