# wikibot.py

# Imports for pycord
import discord
from discord import option

# Imports for dotenv
import os
import dotenv

# Imports for data
from rswiki_wrapper import Latest, TimeSeries, AvgPrice, Mapping
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io

print(f'Loading environment')

dotenv.load_dotenv()

debug_guild = os.environ['DEBUG_GUILD'].split(',')
debug_guild = [int(x) for x in debug_guild]

bot = discord.Bot(debug_guilds=debug_guild)
user_agent = os.getenv('USER_AGENT')

item_mapping = Mapping(user_agent=user_agent)
item_map = {}
for d in item_mapping.content:
    item_map[str(d['id'])] = d
    item_map[d['name']] = d

print(f'Done loading, syncing commands')


def convert_identifier(value):
    """
    This function takes in a list of dictionaries and a value (either an 'id' or a 'name'),
    and returns the 'id' if the provided value is a 'name', or the 'name' if the provided value is an 'id'.
    If no matching dictionary is found, the function returns None.
    """
    value = value.capitalize()
    if value in item_map:
        # If the provided value is a key in the item_map, return the 'name' if the provided value is an 'id'
        # or the 'id' if the provided value is a 'name'
        if value.isnumeric():
            return item_map[value]['name']
        else:
            return item_map[value]['id']
    else:
        return None


@bot.event
async def on_ready():
    await bot.sync_commands()

    print(f'We have logged in as {bot.user}')


@bot.slash_command(name='hello', description='Test Slash Commands and Say Hello')
async def hello(ctx):
    await ctx.respond("Hello!")


@bot.slash_command(description='Documentation on commands')
@option('command', description='Which command to provide help (or all)', required=False, default='all')
async def help(ctx: discord.ApplicationContext, command: str):
    valid_commands = {'all': """Here is a list of valid commands:
`/latest`: Returns the latest real-time price & volume for given items
`/average`: Returns the average real-time price & volume over a specified time period for given items
`/timeseries`: Returns a timeseries graph of the latest 365 price & volume datapoints for a specific time step for a given item
`/itemid`: Look up an item by name to find out the item ID""",
                      'latest': """`latest`
Returns the latest real-time price & volume for given item(s)
Required Parameters: `items` - Provide the item ID(s) or name(s) to provide the latest price & volume for. 
If looking up multiple items, separate with |. Names are not case sensitive""",
                      'average': """`average`
Returns the average real-time price & volume over a specified time period for given items
Required Parameters: `timestep` - The time period to request an average. RSWiki accepts 5m and 1h as valid arguments
`items` - Provide the item ID(s) or name(s) to provide the latest price & volume for. 
If looking up multiple items, separate with |. Names are not case sensitive""",
                      'timeseries': """`timeseries`
Returns a timeseries graph of the latest 365 price & volume datapoints for a specific time step for a given item
Required Parameters: `timestep` - The time step to average data. RSWiki accepts 5m and 1h as valid arguments
`id` OR `name` - The item name or ID. If you provide both, item name will be ignored. Name is case insensitive.
Optional Parameters: `volume`: Boolean - True to include volume graph, False to exclude it
""",
                      'itemid': """`itemid`
Look up an item by name to find out the item ID
Required Parameters: `name` - The item name to look up. Name is case insensitive and can be partial.
'coal' will return 'coal' and 'charcoal' results."""}

    if command in valid_commands.keys():
        await ctx.respond(valid_commands[command])
    else:
        await ctx.respond('Your command is not valid, use `/help` with no command to see valid documented commands')


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
    id_list = id_string.split('|')

    # Iterate over the elements in the list.
    for i, item_id in enumerate(id_list):
        # If the element is numeric, skip it.
        if item_id.isnumeric():
            continue

        # If the element is not numeric, it is a name.
        # Convert the name to a numeric element using the name_conversion function.
        temp_id = convert_identifier(item_id)

        # If the converted element is numeric, replace the original non-numeric element with the numeric element
        # in the id_list array.
        if isinstance(temp_id, int):
            id_list[i] = str(temp_id)
        else:
            id_list.pop(i)

    # Return a string with the same elements as the input string, but with any non-numeric elements converted to
    # numeric elements using the name_conversion function.
    return '|'.join(id_list)


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
        return d.strftime('%d %b %y')
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

    ids = convert_names_to_ids(items)

    if ids is None or ids == '':
        await ctx.respond('Unable to find any valid item IDs that match your request, '
                          'try `/itemid` to look up any partial item names')
        return

    await ctx.defer()
    for item in ids.split('|'):
        item_name = item_map[item]['name']

        real_time = Latest(id=item, user_agent=user_agent)

        embed = discord.Embed(title=f'{item_name} - Latest Prices',
                              url='https://prices.runescape.wiki/osrs/item/'+item)
        embed.set_thumbnail(url='https://oldschool.runescape.wiki/images/'+item_map[item]['icon'].replace(' ', '_'))
        embed.add_field(name=f"Buy Price: {real_time.content[str(item)]['high']}",
                        value=f"{pretty_timestamp(real_time.content[str(item)]['highTime'])}")
        embed.add_field(name=f"Sell Price: {real_time.content[str(item)]['low']}",
                        value=f"{pretty_timestamp(real_time.content[str(item)]['lowTime'])}")

        embed.set_footer(text="Information requested by: {}".format(ctx.author.display_name))
        await ctx.respond(embed=embed)


@bot.slash_command(description='Get 5m or 1h average prices')
@option('items', description='Specific item IDs or names(separate with | for multiple)', required=True)
@option('timestep', description='Choose a timestep (5m or 1h)', required=True, default='5m')
async def average(ctx: discord.ApplicationContext, items: str, timestep: str):

    ids = convert_names_to_ids(items)

    if ids is None or ids == '':
        await ctx.respond('Unable to find any valid item IDs that match your request, '
                          'try `/itemid` to look up any partial item names')
        return

    await ctx.defer()

    real_time = AvgPrice(route=timestep, user_agent=user_agent)

    for item in ids.split('|'):
        item_name = item_map[item]['name']

        embed = discord.Embed(title=f'{item_name} - {timestep} Average Prices',
                              url='https://prices.runescape.wiki/osrs/item/'+item)
        embed.set_thumbnail(url='https://oldschool.runescape.wiki/images/'+item_map[item]['icon'].replace(' ', '_'))
        embed.add_field(name=f"Buy Price: {real_time.content[item]['avgHighPrice']}",
                        value=f"Volume - {real_time.content[item]['highPriceVolume']}")
        embed.add_field(name=f"Sell Price: {real_time.content[item]['avgLowPrice']}",
                        value=f"Volume - {real_time.content[item]['lowPriceVolume']}")

        embed.set_footer(text="Information requested by: {}".format(ctx.author.display_name))
        await ctx.respond(embed=embed)


@bot.slash_command(description='Generate historical pricing')
@option('id', description='Specific itemID', required=False, default='')
@option('name', description='Item name', required=False, default='')
@option('timestep', description='Step for time stamps (5m, 1h, etc)', required=False, default='5m')
@option('volume', description='Include volume? (Default yes)', required=False, default=True)
async def timeseries(ctx: discord.ApplicationContext, id: str, name: str, timestep: str, volume: bool):

    if id == '':
        if name == '':
            await ctx.respond('Must provide a name or an itemID')

        id = str(convert_identifier(name))

    if (id == '') or (id is None):
        await ctx.respond(f'Failed to lookup itemID for {name}, found {id}')
    else:
        if name == '':
            name = convert_identifier(id)

        if 'm' in timestep:
            freq = timestep.strip('m') + 'min'
        elif 'h' in timestep:
            freq = timestep
        else:
            await ctx.respond(f'Invalid timestep {timestep}')
            return

        time_series = TimeSeries(id=id, timestep=timestep, user_agent=user_agent)

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

        if volume:
            fig, axs = plt.subplots(nrows=2, sharex=False, figsize=(15, 10))
            plt.subplots_adjust(hspace=0.5)

            width = np.min(np.diff(mdates.date2num(df[['timestamp'][0]])))

            axs[0].plot('timestamp', 'avgHighPrice', data=df, label='High Price', color='#ffa333')
            axs[0].plot('timestamp', 'avgLowPrice', data=df, label='Low Price', color='#33ff5f')
            axs[0].legend()
            axs[0].set_title(f'Price - {name.capitalize()} - ID {id}')

            axs[1].bar('timestamp', 'highPriceVolume', width=width, data=df, label='High Price Volume', color='#ffa333',
                       ec="k", lw=0.1)
            axs[1].bar('timestamp', 'lowPriceVolume', width=width, data=df, label='Low Price Volume', color='#33ff5f',
                       ec="k", lw=0.1)
            axs[1].legend()
            axs[1].set_title(f'Volume - {name.capitalize()} - ID {id}')

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
                # month-day:
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

            # fig, axes = plt.subplots(nrows=2, figsize=(9, 9))
            # plt.subplots_adjust(hspace=0.4)
            #
            # df.plot(ax=axes[0], x="timestamp", y=['avgHighPrice', 'avgLowPrice'], xlabel='timestamp', ylabel='price')
            # axes[0].set_title(f'Price - ID {id} - {name.capitalize()}')
            #
            # df.plot.bar(ax=axes[1], x="timestamp", y=['highPriceVolume', 'lowPriceVolume'], xlabel='timestamp',
            #             ylabel='volume', stacked=True, width=0.9)
            # axes[1].set_title(f'Volume - ID {id} - {name.capitalize()}')
            # axes[1].xaxis.set_major_locator(ticker.AutoLocator())

        else:
            fig, axs = plt.subplots(figsize=(15, 5))
            df.plot(ax=axs, x="timestamp", y=['avgHighPrice', 'avgLowPrice'], xlabel='timestamp', ylabel='price',
                    color=['#ffa333', '#33ff5f'])
            axs.set_title(f'Price - {name.capitalize()} - ID {id}')
            axs.grid(True, color='0.4')

        # Save content into the data stream
        plt.savefig(data_stream, format='png', bbox_inches="tight", dpi=80)
        plt.close()

        # Create file
        data_stream.seek(0)
        chart = discord.File(data_stream, filename="price_history.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://price_history.png")

        await ctx.respond(file=chart, embed=embed)


@bot.slash_command(name='itemid', description='Lookup the ID of an item')
@option('name', description='Item Name', required=True)
async def id_lookup(ctx: discord.ApplicationContext, name: str):
    response = [(k, v['id']) for k, v in item_map.items() if name.lower() in k.lower()]

    if len(response) > 2000:
        response = 'Cannot provide information for that many itemIDs, try specifying fewer itemIDs'

    await ctx.respond(response)


bot.run(os.getenv('TOKEN'))
