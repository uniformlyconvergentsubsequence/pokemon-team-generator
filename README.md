# 🔥 Smogon Pokemon Team Generator

An AI-powered competitive Pokemon team builder that generates legal, competitive teams for Pokemon Showdown using Smogon data and OpenAI's GPT-4.

## Features

- **AI-Powered Generation**: Uses GPT-4 to create strategic, synergistic Pokemon teams
- **Smogon Integration**: Fetches data from Smogon's competitive databases and usage stats
- **Format Support**: Supports multiple competitive formats (OU, UU, Ubers, etc.)
- **Legal Team Validation**: Ensures all generated teams are legal in the specified format
- **Proper EV Distribution**: Guarantees EVs add up to exactly 506 as required
- **Showdown-Ready**: Outputs teams in the exact format needed for Pokemon Showdown
- **User-Friendly Interface**: Clean, responsive web interface with example prompts

## Quick Start

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Start the Server**:
   ```bash
   npm start
   ```

3. **Visit the Application**:
   Open your browser to `http://localhost:3000`

4. **Generate Teams**:
   - Enter your OpenAI API key
   - Choose a competitive format
   - Describe the team you want
   - Get a perfectly formatted team!

## Usage

### Web Interface

The application provides an intuitive web interface where you can:

- Enter your OpenAI API key (required for AI generation)
- Select from popular competitive formats
- Describe your team requirements using natural language
- Get instant, formatted team builds ready for Pokemon Showdown

### Example Prompts

- "Hyper offensive team with strong physical attackers"
- "Balanced team around Toxapex with good defensive core"
- "Rain team with Swift Swim sweepers and Pelipper"
- "Sand team with Tyranitar and Excadrill"
- "Stall team with maximum bulk and recovery options"

### Supported Formats

- OU (OverUsed)
- Ubers
- UU (UnderUsed)
- RU (RarelyUsed)
- NU (NeverUsed)
- PU
- Monotype
- Anything Goes
- Doubles OU
- VGC 2024

## Output Format

Teams are generated in the exact format required by Pokemon Showdown:

```
Flygon @ Loaded Dice  
Ability: Levitate  
Tera Type: Fire  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Dragon Dance  
- Earthquake  
- Scale Shot  
- Fire Punch  

Galvantula @ Focus Sash  
Ability: Compound Eyes  
Tera Type: Ghost  
EVs: 4 HP / 252 SpA / 252 Spe  
Timid Nature  
IVs: 0 Atk  
- Sticky Web  
- Thunder  
- Bug Buzz  
- Thunder Wave  
```

## API Requirements

- **OpenAI API Key**: You need a valid OpenAI API key with access to GPT-4
- **Internet Connection**: Required to fetch Smogon data and usage statistics

## Development

For development with auto-reload:

```bash
npm run dev
```

## How It Works

1. **User Input**: Takes natural language descriptions of desired teams
2. **Data Fetching**: Retrieves current Smogon format data and usage statistics
3. **AI Generation**: Uses GPT-4 with specialized prompts to generate competitive teams
4. **Validation**: Ensures legal movesets, proper EV distribution, and format compliance
5. **Formatting**: Outputs teams in Pokemon Showdown's required format

## Technical Details

- **Backend**: Node.js with Express
- **AI**: OpenAI GPT-4 API
- **Data Sources**: Smogon Strategy Pokedex and usage statistics
- **Frontend**: Vanilla HTML/CSS/JavaScript with modern responsive design
- **Validation**: Ensures 506 EV totals and format-legal teams

## Security

- API keys are only used for requests and never stored
- All API calls are made server-side to protect user credentials
- No persistent data storage - teams are generated fresh each time

## Contributing

Feel free to contribute improvements, bug fixes, or new features! The codebase is designed to be easily extensible.
