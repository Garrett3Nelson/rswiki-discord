# wikibot.py

# Imports for pycord
import discord
from discord import option

# Imports for dotenv
import os
import dotenv

# Imports for data
from rswiki_wrapper import Latest, TimeSeries, AvgPrice, Mapping
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io

dotenv.load_dotenv()

debug_guild = os.environ['DEBUG_GUILD'].split(',')
debug_guild = [int(x) for x in debug_guild]

bot = discord.Bot(debug_guilds=debug_guild)
user_agent = os.getenv('USER_AGENT')


def convert_identifier(name_or_id: str):
    """
    Converts the input name or id to its corresponding name or id using the RSWiki API Mapping tool

    Args:
        name_or_id (str): A string that represents the name or id to be converted.

    Returns:
        str: The converted name or id, or the string 'No match' if no matching elements were found.
    """

    # Create a Mapping object with the specified user_agent parameter.
    temp_map = Mapping(user_agent=user_agent)

    if name_or_id.isnumeric():
        # If the input name_or_id is numeric (aka an itemID), find the id in the Map
        response = [x['name'] for x in temp_map.json if int(name_or_id) == int(x['id'])]
    else:
        # If the input name_or_id is not numeric (aka an item name), find the name in the map and return the ID
        response = [x['id'] for x in temp_map.json if name_or_id.lower() == x['name'].lower()]

    # If the response list is empty, then no matching elements were found and return the string 'No match'.
    if len(response) == 0:
        return 'No match'

    # Otherwise, return the first element of the response list, which is the id of the matching element.
    return response[0]


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
`/average`: Returns the average real-time price & volume over a specified time period for a given item
`/timeseries`: Returns a timeseries graph of the latest 365 price & volume data for a specific time step for a given item
`/itemid`: Look up an item by name to find out the item ID""",
                      'latest': """`latest`
Returns the latest real-time price & volume for given item(s)
Required Parameters: `items` - Provide the item ID(s) or name(s) to provide the latest price & volume for. If looking up multiple items, separate with |""",
                      'average': """`average`
Returns the average real-time price & volume over a specified time period for a given item
Required Parameters: `timestep` - The time period to request an average. RSWiki accepts 5m and 1h as valid arguments
`id` OR `name` - The item name or ID. If you provide both, item name will be ignored. Name is case insensitive.""",
                      'timeseries': """`timeseries`
Returns a timeseries graph of the last 365 points of price & volume data for a specific time step for a given item
Required Parameters: `timestep` - The time step to average data. RSWiki accepts 5m and 1h as valid arguments
`id` OR `name` - The item name or ID. If you provide both, item name will be ignored. Name is case insensitive.
Optional Parameters: `volume`: 
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
             numeric elements using the name_conversion function. Any elements which fail name_conversion are removed
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


@bot.slash_command(description='Get latest real-time prices')
@option('items', description='Specific item IDs or names(separate with | for multiple)', required=True, default='')
async def latest(ctx: discord.ApplicationContext,
                 items: str):

    ids = convert_names_to_ids(items)

    # if len(ids) == 0:
    #    real_time = Latest(user_agent=user_agent)
    # else:
    real_time = Latest(id=ids, user_agent=user_agent)

    response = json.dumps(real_time.content, indent=4)

    if len(response) > 2000:
        response = 'Cannot provide information for that many itemIDs, try specifying fewer itemIDs'

    await ctx.respond(response)


@bot.slash_command(description='Get 5m or 1h average prices')
@option('id', description='Specific ID', required=False)
@option('name', description='Item name', required=False)
@option('timestep', description='Choose a timestep (5m or 1h)', required=True, default='5m')
async def average(ctx: discord.ApplicationContext,
                 id: str, name: str, timestep: str):

    if (id == '') or (id is None):
        if name == '':
            await ctx.respond('Must provide a name or an itemID')

        id = str(convert_identifier(name))

    if (id == '') or (id is None):
        await ctx.respond(f'Failed to lookup itemID for {name}, found {id}')
    else:
        real_time = AvgPrice(route=timestep, user_agent=user_agent)
        response = json.dumps(real_time.content[id], indent=4)

        if len(response) > 2000:
            response = 'Cannot provide information for that many itemIDs, try specifying fewer itemIDs'

        await ctx.respond(response)


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
        if volume:
            fig, axs = plt.subplots(nrows=2, sharex=False, figsize=(15, 10))
            plt.subplots_adjust(hspace=0.5)

            width = np.min(np.diff(mdates.date2num(df[['timestamp'][0]])))

            axs[0].plot('timestamp', 'avgHighPrice', data=df, label='High Price', lw=0.95, color='orange', )
            axs[0].plot('timestamp', 'avgLowPrice', data=df, label='Low Price', lw=0.95, color='green')
            axs[0].legend()
            axs[0].set_title(f'Price - {name.capitalize()} - ID {id}')

            axs[1].bar('timestamp', 'highPriceVolume', width=width, data=df, label='High Price Volume', color='orange',
                       ec="k", lw=0.1)
            axs[1].bar('timestamp', 'lowPriceVolume', width=width, data=df, label='Low Price Volume', color='green',
                       ec="k", lw=0.1)
            axs[1].legend()
            axs[1].set_title(f'Volume - {name.capitalize()} - ID {id}')

            for nn, ax in enumerate(axs):
                locator = mdates.AutoDateLocator()
                formatter = mdates.ConciseDateFormatter(locator)
                formatter.formats = ['%y',  # ticks are mostly years
                                     '%b',  # ticks are mostly months
                                     '%d',  # ticks are mostly days
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
            plt.figure(figsize=(1, 1))
            trend = df.plot(x="timestamp", y=['avgHighPrice', 'avgLowPrice'], xlabel='timestamp', ylabel='price')
            trend.set_title(f'{id} - {name}')

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
    temp_map = Mapping(user_agent=user_agent)
    response = [(x['id'], x['name']) for x in temp_map.json if name.lower() in x['name'].lower()]

    if len(response) > 2000:
        response = 'Cannot provide information for that many itemIDs, try specifying fewer itemIDs'

    await ctx.respond(response)


bot.run(os.getenv('TOKEN'))
