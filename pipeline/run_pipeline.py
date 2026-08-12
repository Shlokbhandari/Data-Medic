import pandas as pd

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {len(df)}')
    
    # Sort by order_date before dropping duplicates to keep the earliest transaction
    df = df.sort_values(by='order_date')
    # Drop duplicates based on 'transaction_id', keeping the first occurrence (earliest date)
    dropped_duplicates = df[df.duplicated(subset=['transaction_id'], keep='first')]
    if not dropped_duplicates.empty:
        print(f'Dropped {len(dropped_duplicates)} duplicate transactions')
        print(dropped_duplicates)
    df = df.drop_duplicates(subset=['transaction_id'], keep='first')
    df = df.dropna(subset=['price'])
    
    print(f'Rows after cleaning: {len(df)}')
    
    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()