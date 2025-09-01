const express = require('express');
const axios = require('axios');
const { OpenAI } = require('openai');
const cors = require('cors');
const path = require('path');
require('dotenv').config();

const { validateTeam, getFormatPrompt, FORMATS } = require('./utils/pokemon-utils');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Routes
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Generate team endpoint
app.post('/api/generate-team', async (req, res) => {
    try {
        const { prompt, apiKey, format = 'ou' } = req.body;
        
        if (!prompt || !apiKey) {
            return res.status(400).json({ error: 'Prompt and API key are required' });
        }

        // Initialize OpenAI with user's API key
        const openai = new OpenAI({ apiKey });

        // Fetch Smogon data for context
        const smogonData = await fetchSmogonData(format);
        
        // Generate team using OpenAI
        const team = await generateTeamWithAI(openai, prompt, format, smogonData);
        
        res.json({ team });
    } catch (error) {
        console.error('Error generating team:', error);
        res.status(500).json({ error: 'Failed to generate team: ' + error.message });
    }
});

// Fetch available formats
app.get('/api/formats', async (req, res) => {
    try {
        const formats = await fetchAvailableFormats();
        res.json({ formats });
    } catch (error) {
        console.error('Error fetching formats:', error);
        res.status(500).json({ error: 'Failed to fetch formats' });
    }
});

async function fetchSmogonData(format) {
    try {
        // Fetch format data
        const formatUrl = `https://www.smogon.com/dex/sv/formats/${format}/`;
        
        // Fetch usage stats (using a more recent month as fallback)
        let statsUrl = `https://www.smogon.com/stats/2025-01/gen9${format}-1695.txt`;
        
        const [formatResponse, statsResponse] = await Promise.allSettled([
            axios.get(formatUrl, { timeout: 10000 }),
            axios.get(statsUrl, { timeout: 10000 })
        ]);

        let formatData = '';
        let statsData = '';

        if (formatResponse.status === 'fulfilled') {
            formatData = formatResponse.value.data;
        }

        if (statsResponse.status === 'fulfilled') {
            statsData = statsResponse.value.data;
        } else {
            // Try alternative stats URLs if the first fails
            try {
                const altResponse = await axios.get(`https://www.smogon.com/stats/2024-12/gen9${format}-1695.txt`, { timeout: 10000 });
                statsData = altResponse.data;
            } catch (e) {
                console.warn('Could not fetch stats data:', e.message);
            }
        }

        return {
            formatData,
            statsData,
            format
        };
    } catch (error) {
        console.warn('Error fetching Smogon data:', error.message);
        return { formatData: '', statsData: '', format };
    }
}

async function fetchAvailableFormats() {
    // Return formats from our utility module
    return Object.keys(FORMATS).map(key => ({
        value: key,
        name: FORMATS[key].name,
        description: FORMATS[key].description
    }));
}

async function generateTeamWithAI(openai, prompt, format, smogonData) {
    const formatPrompt = getFormatPrompt(format);
    const formatInfo = FORMATS[format.toLowerCase()];
    
    const systemPrompt = `You are an expert Pokemon team builder specializing in Smogon competitive formats. 

CRITICAL FORMATTING REQUIREMENTS:
- Each Pokemon must be formatted EXACTLY like this example:
Flygon @ Loaded Dice  
Ability: Levitate  
Tera Type: Fire  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Dragon Dance  
- Earthquake  
- Scale Shot  
- Fire Punch  

ABSOLUTE RULES YOU MUST FOLLOW:
1. EVs must add up to EXACTLY 506 (not 508, not 504 - exactly 506)
2. All Pokemon, moves, items, and abilities must be legal in the ${format.toUpperCase()} format
3. ${formatInfo?.hasTeraTypes ? 'Include Tera Type for each Pokemon (SV format)' : 'Do NOT include Tera Type (pre-SV format)'}
4. Use proper competitive movesets and items that work in ${format.toUpperCase()}
5. Ensure team synergy and strategy
6. Output exactly 6 Pokemon, separated by blank lines
7. No additional text before or after the team
8. Each Pokemon must have exactly 4 moves (lines starting with -)
9. Include IVs only when relevant (e.g., "IVs: 0 Atk" for special attackers)

${formatPrompt}

COMMON EV SPREADS (all total 506):
- Physical Sweeper: 252 Atk / 4 HP / 252 Spe OR 252 Atk / 4 SpD / 252 Spe
- Special Sweeper: 252 SpA / 4 HP / 252 Spe OR 252 SpA / 4 SpD / 252 Spe
- Physical Wall: 252 HP / 252 Def / 4 SpD
- Special Wall: 252 HP / 4 Def / 252 SpD
- Fast Support: 252 HP / 4 Def / 252 Spe

${smogonData.statsData ? 'I have access to current usage statistics to inform competitive choices.' : ''}

Generate a competitive team that synergizes well and fits the user's request. Focus on creating a balanced team with clear roles and strategies.`;

    const completion = await openai.chat.completions.create({
        model: "gpt-4",
        messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: `Generate a ${format.toUpperCase()} team: ${prompt}` }
        ],
        temperature: 0.7,
        max_tokens: 2500
    });

    const team = completion.choices[0].message.content.trim();
    
    // Validate the team format
    const validatedTeam = validateAndFixTeam(team, format);
    
    return validatedTeam;
}

function validateAndFixTeam(team, format) {
    // First validate using our utility
    const validation = validateTeam(team);
    
    if (validation.valid) {
        return team;
    }
    
    // Basic validation to ensure proper formatting
    const lines = team.split('\n');
    let pokemonCount = 0;
    let currentPokemon = [];
    let validatedTeam = [];

    for (let line of lines) {
        line = line.trim();
        if (!line) {
            if (currentPokemon.length > 0) {
                validatedTeam.push(currentPokemon.join('\n'));
                currentPokemon = [];
                pokemonCount++;
            }
            continue;
        }

        // Check if this is a new Pokemon (contains @)
        if (line.includes('@')) {
            if (currentPokemon.length > 0) {
                validatedTeam.push(currentPokemon.join('\n'));
                pokemonCount++;
            }
            currentPokemon = [line];
        } else {
            currentPokemon.push(line);
        }
    }

    // Add the last Pokemon if exists
    if (currentPokemon.length > 0) {
        validatedTeam.push(currentPokemon.join('\n'));
        pokemonCount++;
    }

    const result = validatedTeam.join('\n\n');
    
    // Log validation results for debugging
    console.log(`Team validation: ${validation.valid ? 'PASSED' : 'FAILED'}`);
    if (!validation.valid) {
        console.log(`Validation error: ${validation.error}`);
    }
    
    return result;
}

app.listen(PORT, () => {
    console.log(`Pokemon Team Generator server running on port ${PORT}`);
    console.log(`Visit http://localhost:${PORT} to use the application`);
});