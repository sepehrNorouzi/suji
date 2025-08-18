import os
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import timedelta

from shop.models import (
    Currency, Asset, Cost, CurrencyPackageItem, 
    RewardPackage, ShopPackage, ShopSection, 
    ShopConfiguration, DailyRewardPackage,
    LuckyWheel, LuckyWheelSection
)
from match.models import MatchType, MatchConfiguration
from shop.choices import AssetType


class Command(BaseCommand):
    help = 'Seed the database with initial data for shop and match systems'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write(self.style.WARNING('Flushing existing data...'))
            self.flush_data()

        with transaction.atomic():
            self.stdout.write(self.style.SUCCESS('Starting data seeding...'))
            
            # Create currencies
            currencies = self.create_currencies()
            
            # Create assets
            assets = self.create_assets()
            
            # Create costs
            costs = self.create_costs(currencies)
            
            # Create currency package items
            currency_items = self.create_currency_items(currencies)
            
            # Create reward packages
            reward_packages = self.create_reward_packages(currency_items, assets)
            
            # Create shop sections and packages
            self.create_shop_system(currencies, currency_items, assets)
            
            # Create daily rewards
            self.create_daily_rewards(reward_packages)
            
            # Create lucky wheel
            self.create_lucky_wheel(reward_packages)
            
            # Create shop configuration
            self.create_shop_configuration(reward_packages)
            
            # Create match system
            self.create_match_system(costs, reward_packages)
            
        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))

    def flush_data(self):
        """Delete existing data"""
        models_to_flush = [
            LuckyWheelSection, LuckyWheel, DailyRewardPackage,
            ShopConfiguration, ShopPackage, ShopSection,
            RewardPackage, CurrencyPackageItem, Cost,
            Asset, Currency, MatchType, MatchConfiguration
        ]
        
        for model in models_to_flush:
            model.objects.all().delete()

    def create_currencies(self):
        """Create game currencies"""
        self.stdout.write('Creating currencies...')
        
        currencies = {}
        
        # In-app currencies
        currencies['coins'] = Currency.objects.create(
            name='Coins',
            type=Currency.CurrencyType.IN_APP,
            config={'description': 'Primary in-game currency'}
        )
        
        currencies['gems'] = Currency.objects.create(
            name='Gems',
            type=Currency.CurrencyType.IN_APP,
            config={'description': 'Premium in-game currency'}
        )
        
        currencies['tickets'] = Currency.objects.create(
            name='Tickets',
            type=Currency.CurrencyType.IN_APP,
            config={'description': 'Match entry tickets'}
        )
        
        # Real currency (for IAP)
        currencies['usd'] = Currency.objects.create(
            name='USD',
            type=Currency.CurrencyType.REAL,
            config={'description': 'US Dollar for in-app purchases'}
        )
        
        self.stdout.write(f'Created {len(currencies)} currencies')
        return currencies

    def create_assets(self):
        """Create game assets"""
        self.stdout.write('Creating assets...')
        
        assets = {}
        
        # Avatar assets
        avatar_configs = [
            {'name': 'Default Avatar', 'config': {'color': 'blue', 'style': 'classic'}},
            {'name': 'Red Avatar', 'config': {'color': 'red', 'style': 'classic'}},
            {'name': 'Green Avatar', 'config': {'color': 'green', 'style': 'classic'}},
            {'name': 'Purple Avatar', 'config': {'color': 'purple', 'style': 'modern'}},
            {'name': 'Gold Avatar', 'config': {'color': 'gold', 'style': 'premium'}},
        ]
        
        for avatar_config in avatar_configs:
            asset_key = avatar_config['name'].lower().replace(' ', '_')
            assets[asset_key] = Asset.objects.create(
                name=avatar_config['name'],
                type=AssetType.AVATAR,
                config=avatar_config['config']
            )
        
        # Sticker assets
        sticker_configs = [
            {'name': 'Happy Face', 'config': {'emoji': '😊', 'category': 'emotions'}},
            {'name': 'Thumbs Up', 'config': {'emoji': '👍', 'category': 'reactions'}},
            {'name': 'Fire', 'config': {'emoji': '🔥', 'category': 'effects'}},
            {'name': 'Brain', 'config': {'emoji': '🧠', 'category': 'sudoku'}},
            {'name': 'Trophy', 'config': {'emoji': '🏆', 'category': 'achievements'}},
        ]
        
        for sticker_config in sticker_configs:
            asset_key = sticker_config['name'].lower().replace(' ', '_')
            assets[asset_key] = Asset.objects.create(
                name=sticker_config['name'],
                type=AssetType.STICKER,
                config=sticker_config['config']
            )
        
        self.stdout.write(f'Created {len(assets)} assets')
        return assets

    def create_costs(self, currencies):
        """Create cost objects for match entries"""
        self.stdout.write('Creating costs...')
        
        costs = {}
        
        # Match entry costs
        costs['free_match'] = Cost.objects.create(
            currency=currencies['tickets'],
            amount=0
        )
        
        costs['casual_match'] = Cost.objects.create(
            currency=currencies['coins'],
            amount=100
        )
        
        costs['ranked_match'] = Cost.objects.create(
            currency=currencies['coins'],
            amount=250
        )
        
        costs['premium_match'] = Cost.objects.create(
            currency=currencies['gems'],
            amount=5
        )
        
        self.stdout.write(f'Created {len(costs)} costs')
        return costs

    def create_currency_items(self, currencies):
        """Create currency package items"""
        self.stdout.write('Creating currency package items...')
        
        items = {}
        
        # Coin packages
        items['coins_small'] = CurrencyPackageItem.objects.create(
            currency=currencies['coins'],
            amount=500,
            config={'package_type': 'small'}
        )
        
        items['coins_medium'] = CurrencyPackageItem.objects.create(
            currency=currencies['coins'],
            amount=1500,
            config={'package_type': 'medium'}
        )
        
        items['coins_large'] = CurrencyPackageItem.objects.create(
            currency=currencies['coins'],
            amount=3500,
            config={'package_type': 'large'}
        )
        
        # Gem packages
        items['gems_small'] = CurrencyPackageItem.objects.create(
            currency=currencies['gems'],
            amount=10,
            config={'package_type': 'small'}
        )
        
        items['gems_medium'] = CurrencyPackageItem.objects.create(
            currency=currencies['gems'],
            amount=30,
            config={'package_type': 'medium'}
        )
        
        items['gems_large'] = CurrencyPackageItem.objects.create(
            currency=currencies['gems'],
            amount=80,
            config={'package_type': 'large'}
        )
        
        # Ticket packages
        items['tickets_small'] = CurrencyPackageItem.objects.create(
            currency=currencies['tickets'],
            amount=5,
            config={'package_type': 'small'}
        )
        
        # Starter packages
        items['starter_coins'] = CurrencyPackageItem.objects.create(
            currency=currencies['coins'],
            amount=1000,
            config={'package_type': 'starter'}
        )
        
        items['starter_gems'] = CurrencyPackageItem.objects.create(
            currency=currencies['gems'],
            amount=5,
            config={'package_type': 'starter'}
        )
        
        items['starter_tickets'] = CurrencyPackageItem.objects.create(
            currency=currencies['tickets'],
            amount=10,
            config={'package_type': 'starter'}
        )
        
        self.stdout.write(f'Created {len(items)} currency package items')
        return items

    def create_reward_packages(self, currency_items, assets):
        """Create reward packages"""
        self.stdout.write('Creating reward packages...')
        
        packages = {}
        
        # Initial wallet package
        packages['initial_wallet'] = RewardPackage.objects.create(
            name='Initial Wallet',
            priority=1,
            reward_type=RewardPackage.RewardType.INIT_WALLET,
            claimable=False,
            config={'description': 'Starting resources for new players'}
        )
        packages['initial_wallet'].currency_items.add(
            currency_items['starter_coins'],
            currency_items['starter_gems'],
            currency_items['starter_tickets']
        )
        packages['initial_wallet'].asset_items.add(assets['default_avatar'])
        
        # Match rewards
        packages['match_winner'] = RewardPackage.objects.create(
            name='Match Winner Reward',
            priority=1,
            reward_type=RewardPackage.RewardType.MATCH_REWARD,
            claimable=False,
            config={'description': 'Reward for winning a match'}
        )
        packages['match_winner'].currency_items.add(currency_items['coins_small'])
        
        packages['match_loser'] = RewardPackage.objects.create(
            name='Match Participation Reward',
            priority=1,
            reward_type=RewardPackage.RewardType.MATCH_REWARD,
            claimable=False,
            config={'description': 'Consolation reward for match participation'}
        )
        
        # Daily reward packages
        for day in range(1, 8):  # 7 days of rewards
            if day == 7:  # Special reward for day 7
                package = RewardPackage.objects.create(
                    name=f'Day {day} Reward - Weekly Bonus',
                    priority=1,
                    reward_type=RewardPackage.RewardType.DAILY_REWARD,
                    claimable=True,
                    config={'description': f'Special weekly bonus for day {day}'}
                )
                package.currency_items.add(currency_items['coins_large'], currency_items['gems_small'])
                if day == 7:
                    package.asset_items.add(assets['gold_avatar'])
            else:
                package = RewardPackage.objects.create(
                    name=f'Day {day} Reward',
                    priority=1,
                    reward_type=RewardPackage.RewardType.DAILY_REWARD,
                    claimable=True,
                    config={'description': f'Daily reward for day {day}'}
                )
                # Scale rewards based on day
                if day <= 3:
                    package.currency_items.add(currency_items['coins_small'])
                else:
                    package.currency_items.add(currency_items['coins_medium'])
            
            packages[f'day_{day}_reward'] = package
        
        # Lucky wheel rewards
        wheel_rewards = [
            ('coins_small', [currency_items['coins_small']]),
            ('coins_medium', [currency_items['coins_medium']]),
            ('gems_small', [currency_items['gems_small']]),
            ('tickets', [currency_items['tickets_small']]),
            ('avatar_red', [assets['red_avatar']]),
            ('avatar_green', [assets['green_avatar']]),
        ]
        
        for reward_key, items in wheel_rewards:
            package = RewardPackage.objects.create(
                name=f'Lucky Wheel - {reward_key.replace("_", " ").title()}',
                priority=1,
                reward_type=RewardPackage.RewardType.LUCKY_WHEEL,
                claimable=False,
                config={'description': f'Lucky wheel reward: {reward_key}'}
            )
            
            for item in items:
                if hasattr(item, 'currency'):  # Currency item
                    package.currency_items.add(item)
                else:  # Asset item
                    package.asset_items.add(item)
            
            packages[f'wheel_{reward_key}'] = package
        
        self.stdout.write(f'Created {len(packages)} reward packages')
        return packages

    def create_shop_system(self, currencies, currency_items, assets):
        """Create shop sections and packages"""
        self.stdout.write('Creating shop system...')
        
        # Create shop sections
        sections = {}
        sections['currency'] = ShopSection.objects.create(
            name='Currency Packs',
            config={'description': 'Buy coins and gems', 'icon': 'currency'}
        )
        
        sections['avatars'] = ShopSection.objects.create(
            name='Avatars',
            config={'description': 'Customize your appearance', 'icon': 'avatar'}
        )
        
        sections['stickers'] = ShopSection.objects.create(
            name='Stickers',
            config={'description': 'Express yourself in matches', 'icon': 'sticker'}
        )
        
        # Currency packages (IAP)
        currency_packages = [
            {
                'name': 'Coin Pack Small',
                'sku': 'coins_small_iap',
                'price_currency': currencies['usd'],
                'price_amount': 0.99,
                'section': sections['currency'],
                'currency_items': [currency_items['coins_small']],
                'priority': 1
            },
            {
                'name': 'Coin Pack Medium',
                'sku': 'coins_medium_iap',
                'price_currency': currencies['usd'],
                'price_amount': 2.99,
                'section': sections['currency'],
                'currency_items': [currency_items['coins_medium']],
                'priority': 2
            },
            {
                'name': 'Gem Pack Small',
                'sku': 'gems_small_iap',
                'price_currency': currencies['usd'],
                'price_amount': 1.99,
                'section': sections['currency'],
                'currency_items': [currency_items['gems_small']],
                'priority': 3
            },
        ]
        
        for package_data in currency_packages:
            package = ShopPackage.objects.create(
                name=package_data['name'],
                sku=package_data['sku'],
                price_currency=package_data['price_currency'],
                price_amount=package_data['price_amount'],
                shop_section=package_data['section'],
                priority=package_data['priority'],
                config={'description': f'Purchase {package_data["name"]}'}
            )
            package.currency_items.add(*package_data['currency_items'])
        
        # Avatar packages (in-app currency)
        avatar_packages = [
            {
                'name': 'Red Avatar',
                'sku': 'avatar_red',
                'price_currency': currencies['coins'],
                'price_amount': 1000,
                'section': sections['avatars'],
                'assets': [assets['red_avatar']],
                'priority': 1
            },
            {
                'name': 'Purple Avatar',
                'sku': 'avatar_purple',
                'price_currency': currencies['gems'],
                'price_amount': 15,
                'section': sections['avatars'],
                'assets': [assets['purple_avatar']],
                'priority': 2
            },
        ]
        
        for package_data in avatar_packages:
            package = ShopPackage.objects.create(
                name=package_data['name'],
                sku=package_data['sku'],
                price_currency=package_data['price_currency'],
                price_amount=package_data['price_amount'],
                shop_section=package_data['section'],
                priority=package_data['priority'],
                config={'description': f'Unlock {package_data["name"]}'}
            )
            package.asset_items.add(*package_data['assets'])
        
        self.stdout.write('Created shop sections and packages')

    def create_daily_rewards(self, reward_packages):
        """Create daily reward configuration"""
        self.stdout.write('Creating daily rewards...')
        
        for day in range(1, 8):
            DailyRewardPackage.objects.create(
                day_number=day,
                reward=reward_packages[f'day_{day}_reward']
            )
        
        self.stdout.write('Created daily reward configuration')

    def create_lucky_wheel(self, reward_packages):
        """Create lucky wheel configuration"""
        self.stdout.write('Creating lucky wheel...')
        
        wheel = LuckyWheel.objects.create(
            name='Daily Lucky Wheel',
            cool_down=timedelta(hours=6),
            config={'description': 'Spin for rewards every 6 hours!'}
        )
        
        # Create wheel sections with different probabilities
        wheel_sections = [
            (reward_packages['wheel_coins_small'], 30),  # 30% chance
            (reward_packages['wheel_coins_medium'], 20), # 20% chance
            (reward_packages['wheel_gems_small'], 15),   # 15% chance
            (reward_packages['wheel_tickets'], 20),      # 20% chance
            (reward_packages['wheel_avatar_red'], 10),   # 10% chance
            (reward_packages['wheel_avatar_green'], 5),  # 5% chance
        ]
        
        for package, chance in wheel_sections:
            LuckyWheelSection.objects.create(
                lucky_wheel=wheel,
                package=package,
                chance=chance
            )
        
        self.stdout.write('Created lucky wheel with 6 sections')

    def create_shop_configuration(self, reward_packages):
        """Create shop configuration"""
        self.stdout.write('Creating shop configuration...')
        
        ShopConfiguration.objects.create(
            player_initial_package=reward_packages['initial_wallet']
        )
        
        self.stdout.write('Created shop configuration')

    def create_match_system(self, costs, reward_packages):
        """Create match types and configuration"""
        self.stdout.write('Creating match system...')
        
        # Create match configuration
        MatchConfiguration.objects.create(
            simultaneous_game=False  # Players can only be in one game at a time
        )
        
        # Create match types
        match_types = [
            {
                'name': 'Practice',
                'priority': 1,
                'entry_cost': costs['free_match'],
                'min_xp': 0,
                'min_cup': 0,
                'min_score': 0,
                'winner_package': None,
                'winner_xp': 50,
                'winner_cup': 0,
                'winner_score': 100,
                'loser_package': None,
                'loser_xp': 10,
                'loser_cup': 0,
                'loser_score': 25,
                'config': {
                    'description': 'Free practice matches for beginners',
                    'difficulty': 'easy',
                    'time_limit': 600  # 10 minutes
                }
            },
            {
                'name': 'Casual',
                'priority': 2,
                'entry_cost': costs['casual_match'],
                'min_xp': 100,
                'min_cup': 0,
                'min_score': 0,
                'winner_package': reward_packages['match_winner'],
                'winner_xp': 100,
                'winner_cup': 10,
                'winner_score': 200,
                'loser_package': reward_packages['match_loser'],
                'loser_xp': 25,
                'loser_cup': 0,
                'loser_score': 50,
                'config': {
                    'description': 'Casual competitive matches',
                    'difficulty': 'medium',
                    'time_limit': 480  # 8 minutes
                }
            },
            {
                'name': 'Ranked',
                'priority': 3,
                'entry_cost': costs['ranked_match'],
                'min_xp': 500,
                'min_cup': 100,
                'min_score': 1000,
                'winner_package': reward_packages['match_winner'],
                'winner_xp': 200,
                'winner_cup': 25,
                'winner_score': 400,
                'loser_package': reward_packages['match_loser'],
                'loser_xp': 50,
                'loser_cup': -5,
                'loser_score': 100,
                'config': {
                    'description': 'Competitive ranked matches',
                    'difficulty': 'hard',
                    'time_limit': 360  # 6 minutes
                }
            },
            {
                'name': 'Tournament',
                'priority': 4,
                'entry_cost': costs['premium_match'],
                'min_xp': 1000,
                'min_cup': 500,
                'min_score': 5000,
                'winner_package': reward_packages['match_winner'],
                'winner_xp': 300,
                'winner_cup': 50,
                'winner_score': 800,
                'loser_package': reward_packages['match_loser'],
                'loser_xp': 75,
                'loser_cup': -10,
                'loser_score': 200,
                'config': {
                    'description': 'Elite tournament matches',
                    'difficulty': 'expert',
                    'time_limit': 300  # 5 minutes
                }
            }
        ]
        
        for match_data in match_types:
            MatchType.objects.create(**match_data)
        
        self.stdout.write(f'Created {len(match_types)} match types')
        self.stdout.write('Created match configuration')
