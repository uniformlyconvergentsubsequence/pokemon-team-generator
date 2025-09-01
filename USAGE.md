# 🎯 Usage Guide

## Getting Started

### Prerequisites
- Node.js 16+ installed
- OpenAI API key (with GPT-4 access)
- Internet connection for Smogon data

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd pokemon-team-generator

# Install dependencies
npm install

# Start the application
npm start
```

Visit `http://localhost:3000` in your browser.

## How to Use

### 1. Enter Your API Key
- Get an OpenAI API key from https://platform.openai.com/
- Enter it in the "OpenAI API Key" field
- Your key is only used for the current request and never stored

### 2. Choose Your Format
- Select from popular competitive formats:
  - **OU (OverUsed)**: Most balanced competitive format
  - **Ubers**: Legendary Pokemon and powerful threats
  - **UU/RU/NU/PU**: Lower tiers with different viable Pokemon
  - **Monotype**: All Pokemon must share a type
  - **VGC**: Official tournament format

### 3. Describe Your Team
Write a natural language description of what you want:

**Good Examples:**
- "Hyper offensive team with strong physical attackers"
- "Rain team with Swift Swim sweepers and Pelipper"
- "Stall team with maximum bulk and recovery options"
- "Balanced team around Toxapex with good type coverage"
- "Sand team featuring Tyranitar and Excadrill"

**Advanced Requests:**
- "Team that beats common OU threats like Dragapult and Garchomp"
- "Trick Room team with slow, powerful attackers"
- "Team built around Baton Pass strategies"
- "Anti-meta team designed to counter current trends"

### 4. Generate and Copy
- Click "Generate Team" and wait 30-60 seconds
- Copy the formatted team directly to Pokemon Showdown
- Use "View Sample Team" to see proper formatting

## Team Format

Generated teams follow Pokemon Showdown's exact format:

```
Pokemon @ Item
Ability: Ability Name
Tera Type: Type (Gen 9 only)
EVs: spread that adds to 506
Nature Name Nature
IVs: 0 Stat (when relevant)
- Move 1
- Move 2
- Move 3
- Move 4
```

## Tips for Better Results

### Prompt Writing
- Be specific about playstyle (offensive, defensive, balanced)
- Mention key Pokemon you want included
- Specify strategies (weather, terrain, status conditions)
- Include counters to specific threats

### Format Considerations
- Higher tiers have more viable options
- Some Pokemon are banned in certain formats
- VGC uses different rules (4 Pokemon teams, restricted legends)

### Team Building Concepts
- **Offensive**: Fast, hard-hitting Pokemon with coverage moves
- **Defensive**: Bulky Pokemon with recovery and status moves
- **Balance**: Mix of offense and defense with good synergy
- **Weather**: Teams built around weather conditions
- **Hazard Control**: Pokemon that set up or remove entry hazards

## Troubleshooting

### Common Issues
1. **API Key Error**: Ensure your OpenAI key has GPT-4 access
2. **Generation Timeout**: Large requests may take longer, be patient
3. **Invalid Team**: Rare AI errors - try regenerating with a clearer prompt
4. **Format Legality**: AI rarely suggests illegal combinations, but double-check

### EV Validation
The app ensures all EV spreads total exactly 506:
- Common spreads: 252/252/4 or 248/252/8
- All generated teams are legal for competitive play

## API Endpoints

- `GET /`: Main application interface
- `POST /api/generate-team`: Generate teams (requires API key)
- `GET /api/sample-team`: View sample formatted team
- `GET /api/formats`: List available formats

## Advanced Features

### Smogon Integration
- Fetches current usage statistics when available
- Uses format-specific legality rules
- Incorporates competitive knowledge from Smogon University

### Validation
- EVs automatically validated (must equal 506)
- Proper Pokemon Showdown formatting guaranteed
- Legal moveset and ability combinations

### Team Analysis
Generated teams include:
- Strategic roles for each Pokemon
- Type coverage analysis
- Synergy considerations
- Meta-game relevance

## Best Practices

1. **Start Simple**: Begin with basic requests, then get more specific
2. **Iterate**: Generate multiple teams and compare strategies
3. **Test**: Import teams into Pokemon Showdown for battle testing
4. **Learn**: Study generated teams to understand competitive concepts
5. **Adapt**: Modify teams based on your playstyle and meta shifts