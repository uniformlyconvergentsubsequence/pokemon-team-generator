// Utility functions for Pokemon team validation and data processing

// Common Pokemon formats and their characteristics
const FORMATS = {
    'ou': {
        name: 'OverUsed',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'The most popular and balanced competitive format'
    },
    'ubers': {
        name: 'Ubers',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'Legendary Pokemon and powerful banned threats'
    },
    'uu': {
        name: 'UnderUsed',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'Pokemon not common enough for OU'
    },
    'ru': {
        name: 'RarelyUsed',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'Pokemon not common enough for UU'
    },
    'nu': {
        name: 'NeverUsed',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'Pokemon not common enough for RU'
    },
    'pu': {
        name: 'PU',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'Pokemon not common enough for NU'
    },
    'monotype': {
        name: 'Monotype',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'All Pokemon must share at least one type'
    },
    'ag': {
        name: 'Anything Goes',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'No restrictions - anything legal in the game goes'
    },
    'doubles': {
        name: 'Doubles OU',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: '2v2 battles with different strategies'
    },
    'vgc2024': {
        name: 'VGC 2024',
        generation: 9,
        hasTeraTypes: true,
        maxEVs: 506,
        description: 'Official tournament format'
    }
};

// Common EV spreads for different roles
const COMMON_EV_SPREADS = {
    'Physical Sweeper': ['252 Atk / 4 HP / 252 Spe', '252 Atk / 4 SpD / 252 Spe'],
    'Special Sweeper': ['252 SpA / 4 HP / 252 Spe', '252 SpA / 4 SpD / 252 Spe'],
    'Physical Wall': ['252 HP / 252 Def / 4 SpD', '248 HP / 252 Def / 8 SpA'],
    'Special Wall': ['252 HP / 4 Def / 252 SpD', '248 HP / 8 Def / 252 SpD'],
    'Mixed Wall': ['252 HP / 4 Def / 252 SpD', '252 HP / 128 Def / 128 SpD'],
    'Fast Support': ['252 HP / 4 Def / 252 Spe', '248 HP / 8 Def / 252 Spe'],
    'Bulky Attacker': ['248 HP / 252 Atk / 8 SpD', '212 HP / 252 Atk / 44 Spe']
};

// Validate EV spread adds up to exactly 506
function validateEVSpread(evString) {
    if (!evString) return false;
    
    // Extract numbers from EV string (e.g., "252 Atk / 4 SpD / 252 Spe")
    const numbers = evString.match(/\d+/g);
    if (!numbers) return false;
    
    const total = numbers.reduce((sum, num) => sum + parseInt(num), 0);
    return total === 506;
}

// Parse and validate a single Pokemon entry
function validatePokemon(pokemonText) {
    const lines = pokemonText.split('\n').map(line => line.trim()).filter(line => line);
    
    if (lines.length < 6) {
        return { valid: false, error: 'Pokemon entry too short' };
    }

    // Check for required components
    const hasItem = lines[0].includes('@');
    const hasAbility = lines.some(line => line.startsWith('Ability:'));
    const hasEVs = lines.some(line => line.startsWith('EVs:'));
    const hasNature = lines.some(line => line.includes('Nature'));
    const hasMoves = lines.some(line => line.startsWith('-'));

    if (!hasItem) return { valid: false, error: 'Missing item (@)' };
    if (!hasAbility) return { valid: false, error: 'Missing ability' };
    if (!hasEVs) return { valid: false, error: 'Missing EVs' };
    if (!hasNature) return { valid: false, error: 'Missing nature' };
    if (!hasMoves) return { valid: false, error: 'Missing moves' };

    // Validate EV spread
    const evLine = lines.find(line => line.startsWith('EVs:'));
    if (evLine) {
        const evSpread = evLine.replace('EVs:', '').trim();
        if (!validateEVSpread(evSpread)) {
            return { valid: false, error: `Invalid EV spread: ${evSpread}` };
        }
    }

    // Count moves
    const moves = lines.filter(line => line.startsWith('-'));
    if (moves.length !== 4) {
        return { valid: false, error: `Expected 4 moves, found ${moves.length}` };
    }

    return { valid: true, pokemon: pokemonText };
}

// Validate entire team
function validateTeam(teamText) {
    const pokemonEntries = teamText.split('\n\n').filter(entry => entry.trim());
    
    if (pokemonEntries.length !== 6) {
        return {
            valid: false,
            error: `Expected 6 Pokemon, found ${pokemonEntries.length}`
        };
    }

    const validation_results = [];
    for (let i = 0; i < pokemonEntries.length; i++) {
        const result = validatePokemon(pokemonEntries[i]);
        validation_results.push({
            index: i + 1,
            ...result
        });
        
        if (!result.valid) {
            return {
                valid: false,
                error: `Pokemon ${i + 1}: ${result.error}`,
                details: validation_results
            };
        }
    }

    return {
        valid: true,
        pokemon_count: pokemonEntries.length,
        details: validation_results
    };
}

// Generate format-specific AI prompt enhancement
function getFormatPrompt(format) {
    const formatInfo = FORMATS[format.toLowerCase()];
    if (!formatInfo) {
        return '';
    }

    let prompt = `Format: ${formatInfo.name} (${format.toUpperCase()})\n`;
    prompt += `Description: ${formatInfo.description}\n`;
    
    if (formatInfo.hasTeraTypes) {
        prompt += `- Include Tera Type for each Pokemon (Gen 9)\n`;
    }
    
    prompt += `- EVs must total exactly ${formatInfo.maxEVs}\n`;
    prompt += `- Use competitive movesets appropriate for ${formatInfo.name}\n`;
    
    return prompt;
}

// Common Pokemon types for type-themed teams
const POKEMON_TYPES = [
    'Normal', 'Fire', 'Water', 'Electric', 'Grass', 'Ice',
    'Fighting', 'Poison', 'Ground', 'Flying', 'Psychic', 'Bug',
    'Rock', 'Ghost', 'Dragon', 'Dark', 'Steel', 'Fairy'
];

// Weather and terrain setters for themed teams
const WEATHER_SETTERS = {
    'Rain': ['Pelipper', 'Politoed'],
    'Sun': ['Torkoal', 'Ninetales-Alola', 'Charizard'],
    'Sand': ['Tyranitar', 'Hippowdon', 'Excadrill'],
    'Hail/Snow': ['Ninetales-Alola', 'Abomasnow'],
    'Psychic Terrain': ['Indeedee', 'Tapu Lele'],
    'Grassy Terrain': ['Tapu Bulu', 'Rillaboom'],
    'Electric Terrain': ['Tapu Koko', 'Pincurchin'],
    'Misty Terrain': ['Tapu Fini', 'Clefairy']
};

module.exports = {
    FORMATS,
    COMMON_EV_SPREADS,
    POKEMON_TYPES,
    WEATHER_SETTERS,
    validateEVSpread,
    validatePokemon,
    validateTeam,
    getFormatPrompt
};