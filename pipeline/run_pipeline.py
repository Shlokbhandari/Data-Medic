import pandas as pd
import os

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {len(df)}')

    df = df.drop_duplicates(subset=['transaction_id'])
    
    missing_price_df = df[df['price'].isna()].copy()
    missing_price_df['flag_reason'] = 'missing price'
    
    if not missing_price_df.empty:
        if os.path.exists('data/flagged_orders.csv'):
            missing_price_df.to_csv('data/flagged_orders.csv', index=False, mode='a', header=False)
        else:
            missing_price_df.to_csv('data/flagged_orders.csv', index=False)
    
    df = df.dropna(subset=['price'])
    
    print(f'Rows after cleaning: {len(df)}')

    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()