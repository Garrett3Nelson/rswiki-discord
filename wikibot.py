# wikibot.py

# Imports for pycord
import discord
import rswiki_wrapper
from discord import option

# Imports for dotenv
import os
import dotenv

# Imports for data
from rswiki_wrapper import Latest, TimeSeries, AvgPrice, Mapping
import json
import pandas as pd
import matplotlib.pyplot as plt
import io

dotenv.load_dotenv()

debug_guild = os.environ['DEBUG_GUILD'].split(',')
debug_guild = [int(x) for x in debug_guild]

bot = discord.Bot(debug_guilds=debug_guild)
user_agent = os.getenv('USER_AGENT')


def name_conversion(name):
    temp_map = Mapping(user_agent=user_agent)
    response = [x['id'] for x in temp_map.json if name.lower() == x['name'].lower()]

    if len(response) == 0:
        return 'No match'

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
`/latest`: Returns the latest real-time price & volume for a given item
`/average`: Returns the average real-time price & volume over a specified time period for a given item
`/timeseries`: Returns a timeseries graph of the latest 365 price & volume data for a specific time step for a given item
`/itemid`: Look up an item by name to find out the item ID""",
                      'latest': """Returns the latest real-time price & volume for a given item
Required Parameters: None (defaults to `all`)
Optional Parameters: `ids` - Provide the itemID(s) to provide the latest price & volume for. If looking up multiple items, separate with |""",
                      'average': """Returns the average real-time price & volume over a specified time period for a given item
Required Parameters: `timestep` - The time period to request an average. RSWiki accepts 5m and 1h as valid arguments
`id` OR `name` - The item name or ID. If you provide both, item name will be ignored. Name is case insensitive.""",
                      'timeseries': """Returns a timeseries graph of the last 365 points of price & volume data for a specific time step for a given item
Required Parameters: `timestep` - The time step to average data. RSWiki accepts 5m and 1h as valid arguments
`id` OR `name` - The item name or ID. If you provide both, item name will be ignored.Name is case insensitive.""",
                      'itemid': """Look up an item by name to find out the item ID
Required Parameters: `name` - The item name to look up. Name is case insensitive and can be partial.
'coal' will return 'coal' and 'charcoal' results."""}

    if command in valid_commands.keys():
        await ctx.respond(valid_commands[command])
    else:
        await ctx.respond('Your command is not valid, use `/help` with no command to see valid documented commands')


@bot.slash_command(description='Get latest real-time prices')
@option('ids', description='Specific IDs (separate with |) or blank for all', required=False, default='')
async def latest(ctx: discord.ApplicationContext,
                 ids: str):

    if len(ids) == 0:
        real_time = Latest(user_agent=user_agent)
    else:
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

        id = str(name_conversion(name))

    if (id == '') or (id is None):
        await ctx.respond(f'Failed to lookup itemID for {name}, found {id}')
    else:
        real_time = AvgPrice(route=timestep, user_agent=user_agent)
        response = json.dumps(real_time.content[id], indent=4)

        if len(response) > 2000:
            response = 'Cannot provide information for that many itemIDs, try specifying fewer itemIDs'

        await ctx.respond(response)


@bot.slash_command(description='Generate historical pricing')
@option('id', description='Specific itemID', required=False)
@option('name', description='Item name', required=False)
@option('timestep', description='Step for time stamps (5m, 1h, etc)', required=False, default='5m')
async def timeseries(ctx: discord.ApplicationContext, id: str, name:str, timestep: str):

    if (id == '') or (id is None):
        if name == '':
            await ctx.respond('Must provide a name or an itemID')

        id = name_conversion(name)

    if (id == '') or (id is None):
        await ctx.respond(f'Failed to lookup itemID for {name}, found {id}')
    else:
        time_series = TimeSeries(id=id, timestep=timestep, user_agent=user_agent)

        # Format the data
        df = pd.DataFrame(time_series.content)
        # Turn unix time into normal datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

        # Initialize IO
        data_stream = io.BytesIO()

        # Do plotting
        plt.figure(figsize=(1, 1))
        trend = df.plot(x="timestamp", y=['avgHighPrice', 'avgLowPrice'])

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
