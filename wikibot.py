# wikibot.py

# Imports for pycord
import discord
from discord import option

# Imports for dotenv
import os
import dotenv

# Imports for data
from rswiki_wrapper import Latest, TimeSeries, AvgPrice, Mapping, MediaWiki
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
from urllib.parse import quote

# Helper imports
import logging

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s: %(message)s', level=logging.INFO)
logging.info('Loading environment')

dotenv.load_dotenv()

user_agent = os.getenv('USER_AGENT')
if user_agent is None:
    user_agent = 'RSWiki Bot Default'
    logging.info('Using default user_agent')

item_mapping = Mapping(user_agent=user_agent)
item_map = {}
for d in item_mapping.content:
    item_map[str(d['id'])] = d
    item_map[d['name']] = d

logging.info('Done loading, syncing commands')

debug_guild = []
bot = discord.Bot(debug_guilds=debug_guild)


def item_to_tuple(value: str):
    """
    This function takes in a value (either an 'id' or a 'name'), and returns a tuple of (item_id, item_name).
    If no matching dictionary is found, the function returns None.
    """
    value = value.capitalize()
    if value in item_map:
        return str(item_map[value]['id']), item_map[value]['name']
    else:
        return None, None


@bot.event
async def on_ready():
    await bot.sync_commands()

    logging.info(f'We have logged in as {bot.user}')


@bot.event
async def on_application_command(command):
    logging.info(f'Received from {command.author} at {command.guild}: {command.command} with options '
                 f'{command.selected_options}')


@bot.slash_command(name='hello', description='Test Slash Commands and Say Hello')
async def hello(ctx):
    await ctx.respond("Hello!")


@bot.slash_command(name='help', description='Documentation on commands')
@option('command', description='Which command to provide help (or all)', required=False, default='all')
async def bot_help(ctx: discord.ApplicationContext, command: str):
    embed = discord.Embed(title=f'Help - {command.capitalize()}')
    # embed.set_thumbnail(url='https://oldschool.runescape.wiki/images/' + item_map[item_name]['icon'].replace(' ', '_'))

    valid_commands = ['all', 'latest', 'average', 'timeseries', 'property_lookup', 'search', 'itemid']

    if command not in valid_commands:
        logging.warning(f'Help: User {ctx.author} submitted {command} which is not in the valid commands array')
        await ctx.respond('Your command is not valid, use `/help` with no command to see valid documented commands')
        return

    # Running w/ python 3.9 which doesn't support case statements, do many if/then
    if command == 'all':
        embed.add_field(name=f"List of valid commands",
                        value="""`/latest`: Returns the latest real-time price for given items
`/average`: Returns the average real-time price & volume over a specified time period for given items
`/timeseries`: Returns a timeseries graph of the latest 365 price & volume datapoints for a specific time step for a given item
`/property_lookup`: Returns properties and their values for any item.
`/search`: Searches the RSWiki and returns the page embed.
`/itemid`: Look up an item by name to find out the item ID""")

    elif command == 'latest':
        embed.add_field(name=f"OSRS Real-Time Latest Price",
                        value="Returns the latest real-time price for given item(s)", inline=False)
        embed.add_field(name=f"Arguments",
                        value="`items` - The item name(s) or ID(s) (or a combination) to provide information on. "
                              "Separate multiple entries with |. Names are not case sensitive but must be spelled "
                              "exactly correct", inline=False)
        embed.add_field(name=f"Sample usage",
                        value="`/latest items:2|coal", inline=False)

    elif command == 'average':
        embed.add_field(name=f"OSRS Real-Time Average Price",
                        value="Returns the latest real-time price and volume average for given item(s) over a given "
                              "time period", inline=False)
        embed.add_field(name=f"Arguments",
                        value="`items` and `timestep`", inline=False)
        embed.add_field(name='items', value="The item name(s) or ID(s) (or a combination) to provide information on. "
                                            "Separate multiple entries with |. Names are not case sensitive but must "
                                            "be spelled exactly correct", inline=True)
        embed.add_field(name='timestep (optional)',
                        value="The time period to provide the average for. 5m and 1h are the accepted"
                        "values by RSWiki. Default 5m if not provided", inline=True)
        embed.add_field(name=f"Sample usage",
                        value="`/average items:coal timestep:5m`", inline=False)

    elif command == 'timeseries':
        embed.add_field(name=f"OSRS Real-Time Timeseries Graph",
                        value="Returns a graph showing the last 365 price & volume points for a specific"
                        "item and a specific time step", inline=False)
        embed.add_field(name=f"Arguments",
                        value="`item`, `timestep`, `volume`", inline=False)
        embed.add_field(name='item', value="The item name or ID to provide information on. Names are not case "
                                           "sensitive but must be spelled exactly correct", inline=True)
        embed.add_field(name='timestep (optional)',
                        value="The time period to provide the average for. 5m and 1h are the accepted"
                        "values by RSWiki. Default 5m if not provided", inline=True)
        embed.add_field(name='volume (optional)',
                        value="True to include volume information, False for only price information. Default True",
                        inline=True)
        embed.add_field(name=f"Sample usage",
                        value="`/timeseries items:coal timestep:5m, volume:True`", inline=False)

    elif command == 'property_lookup':
        embed.add_field(name=f"RS3 or OSRS Item Property Lookup",
                        value="Returns a selection of properties for a given item", inline=False)
        embed.add_field(name=f"Arguments",
                        value="`item`, `game`, `prop`", inline=False)
        embed.add_field(name='item', value="The item name or ID to provide information on. Names are not case "
                                           "sensitive but must be spelled exactly correct", inline=True)
        embed.add_field(name='game',
                        value="The game to look up. OSRS or RS3 (not case sensitive). Default OSRS", inline=True)
        embed.add_field(name='prop (optional)',
                        value="The property(ies) to display. Attempts to match partial names (ex. 'id' matches "
                              "'item_id'). Leave blank to display all properties. If listing multiple properties, "
                              "split with |",
                        inline=True)
        embed.add_field(name=f"Sample usage",
                        value="`/property_lookup item:coal game:osrs`", inline=False)

    elif command == 'search':
        embed.add_field(name=f"RS3 or OSRS Page Search",
                        value="Returns the search result for the given page", inline=False)
        embed.add_field(name=f"Arguments",
                        value="`page` and `game`", inline=False)
        embed.add_field(name='page', value="The page to search. Not case sensitive. Returns the closest match",
                        inline=True)
        embed.add_field(name='game',
                        value="The game to look up. OSRS or RS3 (not case sensitive). Default OSRS", inline=True)
        embed.add_field(name=f"Sample usage",
                        value="`/search page:coal game:osrs`", inline=False)

    elif command == 'itemid':
        embed.add_field(name=f"OSRS Item mapping lookup",
                        value="Look up an item by name to find out the item ID", inline=False)
        embed.add_field(name=f"Arguments",
                        value="`name` - The item name to pair with an ID. Provides all partial name matches. Names "
                              "are not case sensitive", inline=False)
        embed.add_field(name=f"Sample usage",
                        value="`/itemid name:crystal", inline=False)

    embed.set_author(name=ctx.author.display_name, url=ctx.author.jump_url, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="RSWiki Bot is created by Garrett#8250")
    await ctx.respond(embed=embed)


def convert_names_to_ids(id_string: str):
    """
    Converts any non-numeric elements in the input string to numeric elements using the name_conversion function, and
    then returns a new string with the numeric elements.

    Args:
        id_string (str): A string formatted '1|2|3' or 'Test|Text|Name'

    Returns:
        str: A new string with the same elements as the input string, but with any non-numeric elements converted to
             numeric elements using the convert_identifier function. Any elements which fail name_conversion are removed
    """

    # Split the input string into a list of elements.
    item_list = id_string.split('|')

    # Iterate over the elements in the list.
    for i, item in enumerate(item_list):
        # If the element is numeric, skip it.
        logging.debug(f'Checking {item}')
        if item.isnumeric():
            continue

        # If the element is not numeric, it is a name.
        # Convert the name to a numeric element function.
        temp_id, temp_name = item_to_tuple(item)
        logging.debug(f'Got {temp_id}, {temp_name}')
        # If the converted element is numeric, replace the original non-numeric element with the numeric element
        # in the id_list array.
        if temp_id.isnumeric():
            item_list[i] = str(temp_id)
        else:
            item_list.pop(i)

    # Return a string with the same elements as the input string, but with any non-numeric elements converted to
    # numeric elements using the name_conversion function.
    return '|'.join(item_list)


def pretty_timestamp(timestamp):
    """
    This function takes in a Unix timestamp in seconds, and returns a human-readable relative timestamp (e.g. "3 minutes ago")
    """

    # Convert the timestamp to a datetime object
    timestamp_dt = datetime.fromtimestamp(timestamp)

    # Get the current date and time
    now = datetime.now()

    # Calculate the difference between the two datetime objects
    diff = now - timestamp_dt

    s = diff.seconds
    if diff.days > 7 or diff.days < 0:
        return timestamp_dt.strftime('%d %b %y')
    elif diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '{} days ago'.format(diff.days)
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{} seconds ago'.format(s)
    elif s < 120:
        return '1 minute ago'
    elif s < 3600:
        return '{} minutes ago'.format(int(s / 60))
    elif s < 7200:
        return '1 hour ago'
    else:
        return '{} hours ago'.format(int(s / 3600))


@bot.slash_command(description='Get latest real-time prices')
@option('items', description='Specific item IDs or names(separate with | for multiple)', required=True)
async def latest(ctx: discord.ApplicationContext,
                 items: str):
    logging.debug(f'Input {items}')
    ids = convert_names_to_ids(items)

    if ids is None or ids == '':
        logging.warning(f'Latest: User {ctx.author} submitted {items} which converted to {ids} and broke '
                        f'/latest')
        await ctx.respond('Unable to find any valid item IDs that match your request, '
                          'try `/itemid` to look up any partial item names')
        return

    await ctx.defer()

    logging.debug(f'Looking up {ids}')
    real_time = Latest(user_agent=user_agent)
    for item in ids.split('|'):
        item_name = item_map[item]['name']
        rt_latest = real_time.content.get(item)

        embed = discord.Embed(title=f'{item_name} - Latest Prices',
                              url='https://prices.runescape.wiki/osrs/item/' + item)
        embed.set_thumbnail(
            url='https://oldschool.runescape.wiki/images/' + item_map[item_name]['icon'].replace(' ', '_'))

        embed.add_field(name=f"Buy Price: {rt_latest['high']}",
                        value=f"{pretty_timestamp(rt_latest['highTime'])}")
        embed.add_field(name=f"Sell Price: {rt_latest['low']}",
                        value=f"{pretty_timestamp(rt_latest['lowTime'])}")

        embed.set_author(name=ctx.author.display_name, url=ctx.author.jump_url, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="RSWiki Bot is created by Garrett#8250")
        await ctx.respond(embed=embed)


@bot.slash_command(description='Get 5m or 1h average prices')
@option('items', description='Specific item IDs or names(separate with | for multiple)', required=True)
@option('timestep', description='Choose a timestep (5m or 1h)', required=True, default='5m')
async def average(ctx: discord.ApplicationContext, items: str, timestep: str):
    try:
        ids = convert_names_to_ids(items)
    except TypeError:
        logging.warning(f'Average: User {ctx.author} submitted {items} which threw a TypeError when '
                        f'converting ids')
        await ctx.respond('Failed item lookup, ensure you are using a valid item name or ID')
        return

    if ids is None or ids == '':
        logging.warning(f'Average: User {ctx.author} submitted {items} which converted to {ids} and will '
                        f'not work with the request')
        await ctx.respond('Unable to find any valid item IDs that match your request, '
                          'try `/itemid` to look up any partial item names')
        return

    await ctx.defer()

    try:
        real_time = AvgPrice(route=timestep, user_agent=user_agent)
    except KeyError:
        logging.warning(f'Average: User {ctx.author} submitted {timestep} which threw a KeyError when '
                        f'trying to pull average price')
        await ctx.respond('Failed price lookup, ensure you are using a valid timestep (5m, 1h)')
        return

    for item in ids.split('|'):
        item_name = item_map[item]['name']

        embed = discord.Embed(title=f'{item_name} - {timestep} Average Prices',
                              url='https://prices.runescape.wiki/osrs/item/' + item)
        embed.set_thumbnail(url='https://oldschool.runescape.wiki/images/' + item_map[item]['icon'].replace(' ', '_'))
        embed.add_field(name=f"Buy Price: {real_time.content[item]['avgHighPrice']}",
                        value=f"Volume - {real_time.content[item]['highPriceVolume']}")
        embed.add_field(name=f"Sell Price: {real_time.content[item]['avgLowPrice']}",
                        value=f"Volume - {real_time.content[item]['lowPriceVolume']}")

        embed.set_author(name=ctx.author.display_name, url=ctx.author.jump_url, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="RSWiki Bot is created by Garrett#8250")

        await ctx.respond(embed=embed)


@bot.slash_command(description='Generate historical pricing')
@option('item', description='Item name or item ID', required=True)
@option('timestep', description='Step for time stamps (5m, 1h)', required=False, default='5m')
@option('volume', description='Include volume? (Default yes)', required=False, default=True)
async def timeseries(ctx: discord.ApplicationContext, item: str, timestep: str, volume: bool):
    item_id, item_name = item_to_tuple(item)

    if item_id is None or item_name is None:
        logging.warning(f'Timeseries: User {ctx.author} submitted {item} which converted to '
                        f'({item_id}, {item_name}) is not a valid item pair')
        await ctx.respond('Unable to find any valid items that match your request, '
                          'try `/itemid` to look up any partial item names')
        return

    if 'm' in timestep:
        freq = timestep.strip('m') + 'min'
    elif 'h' in timestep:
        freq = timestep
    else:
        logging.warning(f'Timeseries: User {ctx.author} submitted {timestep} which is invalid')
        await ctx.respond(f"Invalid timestep '{timestep}'")
        return

    try:
        time_series = TimeSeries(id=item_id, timestep=timestep, user_agent=user_agent)
    except KeyError:
        logging.warning(f'Average: User {ctx.author} submitted {timestep}  and {item} which threw a '
                        f'KeyError when trying to pull average price')
        await ctx.respond('Failed lookup, ensure you are using a valid item and timestep (5m, 1h)')
        return

    # Format the data
    df = pd.DataFrame(time_series.content)

    await ctx.defer()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

    # Add any missing intervals, format unix to datetime
    start = pd.to_datetime(df[['timestamp'][0]].min(), unit='s')
    end = pd.to_datetime(df[['timestamp'][0]].max(), unit='s')
    dates = pd.date_range(start=start, end=end, freq=freq).to_pydatetime()

    df = df.set_index('timestamp').reindex(dates).reset_index().reindex(columns=df.columns)

    # Fill any NaN entries
    df[['avgHighPrice', 'avgLowPrice']] = df[['avgHighPrice', 'avgLowPrice']].fillna(method='ffill')
    df[['highPriceVolume', 'lowPriceVolume']] = df[['highPriceVolume', 'lowPriceVolume']].fillna(0)

    # Invert lowPriceVolume
    df[['lowPriceVolume']] = df[['lowPriceVolume']] * -1

    # Initialize IO
    data_stream = io.BytesIO()

    # Do plotting

    plt.style.use('dark_background')

    # More involved subplotting for price and volume data
    if volume:
        fig, axs = plt.subplots(nrows=2, sharex=False, figsize=(15, 10))
        plt.subplots_adjust(hspace=0.5)

        width = np.min(np.diff(mdates.date2num(df[['timestamp'][0]])))

        axs[0].plot('timestamp', 'avgHighPrice', data=df, label='High Price', color='#ffa333')
        axs[0].plot('timestamp', 'avgLowPrice', data=df, label='Low Price', color='#33ff5f')
        axs[0].legend()
        axs[0].set_title(f'Price - {item_name.capitalize()} - ID {item_id}')

        axs[1].bar('timestamp', 'highPriceVolume', width=width, data=df, label='High Price Volume', color='#ffa333',
                   ec="k", lw=0.1)
        axs[1].bar('timestamp', 'lowPriceVolume', width=width, data=df, label='Low Price Volume', color='#33ff5f',
                   ec="k", lw=0.1)
        axs[1].legend()
        axs[1].set_title(f'Volume - {item_name.capitalize()} - ID {item_id}')

        for nn, ax in enumerate(axs):
            locator = mdates.AutoDateLocator()
            formatter = mdates.ConciseDateFormatter(locator)
            formatter.formats = ['%y',  # ticks are mostly years
                                 '%b %d',  # ticks are mostly months
                                 '%b %d',  # ticks are mostly days
                                 '%H:%M',  # hrs
                                 '%H:%M',  # min
                                 '', ]  # secs
            # these are mostly just the level above...
            formatter.zero_formats = [''] + formatter.formats[:-1]
            # ...except for ticks that are mostly hours, then it is nice to have
            # day-month:
            formatter.zero_formats[3] = '%d-%b'

            formatter.offset_formats = ['',
                                        '%Y',
                                        '%b %Y',
                                        '%d %b %Y',
                                        '%d %b %Y',
                                        '%d %b %Y %H:%M', ]

            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            ax.set_xlim(left=df[['timestamp'][0]].min(), right=df[['timestamp'][0]].max())
            plt.setp(ax.get_xticklabels(), visible=True, rotation=30)
            ax.grid(True, color='0.4')

    else:
        fig, axs = plt.subplots(figsize=(15, 5))
        df.plot(ax=axs, x="timestamp", y=['avgHighPrice', 'avgLowPrice'], xlabel='timestamp', ylabel='price',
                color=['#ffa333', '#33ff5f'])
        axs.set_title(f'Price - {item_name.capitalize()} - ID {item_id}')
        axs.grid(True, color='0.4')

    # Save content into the data stream
    plt.savefig(data_stream, format='png', bbox_inches="tight", dpi=80)
    plt.close()

    # Create file
    data_stream.seek(0)
    chart = discord.File(data_stream, filename="price_history.png")

    # Populate Embed item
    embed = discord.Embed(title=f'{item_name.capitalize()} - {timestep} Timeseries',
                          url=f'https://prices.runescape.wiki/osrs/item/{item_id}')
    embed.set_thumbnail(url='https://oldschool.runescape.wiki/images/' + item_map[item_id]['icon'].replace(' ', '_'))
    embed.set_author(name=ctx.author.display_name, url=ctx.author.jump_url, icon_url=ctx.author.display_avatar.url)
    embed.set_image(url="attachment://price_history.png")

    await ctx.respond(file=chart, embed=embed)


@bot.slash_command(description='Look up item property(ies)')
@option('item', description='Which item name or item ID to look up', required=True)
@option('game', description='OSRS or RS3', required=True, default='osrs')
@option('prop', description='Which property(ies) to look up (separate with |)', required=False, default='all')
async def property_lookup(ctx: discord.ApplicationContext, item: str, game: str, prop: str):
    item_id, item_name = item_to_tuple(item)

    if item_id is None or item_name is None:
        logging.warning(f'Property_lookup: User {ctx.author} submitted {item} which converted to '
                        f'({item_id}, {item_name}) is not a valid item pair')
        await ctx.respond('Unable to find any valid items that match your request, '
                          'try `/itemid` to look up any partial item names')
        return

    game = game.lower()
    if game == 'osrs':
        game_link = 'https://oldschool.runescape.wiki/'
    elif game == 'rs3':
        game_link = 'https://runescape.wiki/'
    else:
        logging.warning(f'Property_lookup: User {ctx.author} submitted {game} which is not valid')
        await ctx.respond('Invalid game selection, use OSRS or RS3')
        return

    await ctx.defer()

    properties = MediaWiki(game.lower(), user_agent=user_agent)
    properties.browse_properties(item_name)
    properties._clean_properties()

    properties.content = {k.lower(): v for k, v in properties.content.items()}

    embed = discord.Embed(title=f'{item_name} - Properties',
                          url=game_link + 'w/' + item_name.replace(' ', '_'))
    embed.set_thumbnail(url=game_link + 'images/' + item_map[item_name]['icon'].replace(' ', '_'))

    if prop == 'all':
        to_show = list(properties.content.keys())
    else:
        to_show = prop.split('|')

    for p in to_show:
        keys = [a for a in properties.content.keys() if p.lower() in a.lower()]
        if keys:
            for key in keys:
                embed.add_field(name=f"{key.capitalize()}",
                                value=f'{properties.content.get(key)}')

    if not embed.fields:
        embed.add_field(name="No properties found",
                        value='Try using another prop filter or use `all` to see a list of properties')

    embed.set_author(name=ctx.author.display_name, url=ctx.author.jump_url, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="RSWiki Bot is created by Garrett#8250")

    await ctx.respond(embed=embed)


@bot.slash_command(name='search', description='Search the wiki for a page')
@option('page', description='What page to search for', required=True)
@option('game', description='OSRS or RS3', required=True, default='osrs')
async def wiki_search(ctx: discord.ApplicationContext, page: str, game: str):
    game = game.lower()
    if game == 'osrs':
        game_link = 'https://oldschool.runescape.wiki/'
    elif game == 'rs3':
        game_link = 'https://runescape.wiki/'
    else:
        logging.warning(f'Property_lookup: User {ctx.author} submitted {game} which is not valid')
        await ctx.respond('Invalid game selection, use OSRS or RS3')
        return

    await ctx.respond(f'{game_link}?search={quote(page)}')


@bot.slash_command(name='itemid', description='Lookup the ID of an item')
@option('name', description='Item Name', required=True)
async def id_lookup(ctx: discord.ApplicationContext, name: str):
    response = [(k, v['id']) for k, v in item_map.items() if name.lower() in k.lower()]

    if len(response) > 2000:
        response = 'Cannot provide information for that many itemIDs, try specifying fewer itemIDs'

    await ctx.respond(response)


if __name__ == '__main__':
    bot.run(os.getenv('TOKEN'))
