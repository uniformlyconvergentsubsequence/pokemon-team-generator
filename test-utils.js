// Simple test for Pokemon utilities
const { validateEVSpread, validatePokemon, validateTeam, getFormatPrompt } = require('./utils/pokemon-utils');

console.log('Testing Pokemon Team Generator utilities...\n');

// Test EV spread validation
console.log('1. Testing EV spread validation:');
console.log('Valid spread (252 + 4 + 252 = 508): SHOULD FAIL');
console.log(validateEVSpread('252 Atk / 4 HP / 252 Spe')); // Should be false (508 total)

console.log('Valid spread (252 + 2 + 252 = 506): SHOULD PASS');
console.log(validateEVSpread('252 Atk / 2 HP / 252 Spe')); // Should be true (506 total)

console.log('Valid spread (248 + 8 + 252 = 508): SHOULD FAIL');
console.log(validateEVSpread('248 HP / 8 Def / 252 Spe')); // Should be false (508 total)

console.log('Valid spread (248 + 6 + 252 = 506): SHOULD PASS');
console.log(validateEVSpread('248 HP / 6 Def / 252 Spe')); // Should be true (506 total)

// Test single Pokemon validation
console.log('\n2. Testing single Pokemon validation:');
const validPokemon = `Flygon @ Loaded Dice  
Ability: Levitate  
Tera Type: Fire  
EVs: 248 Atk / 6 SpD / 252 Spe  
Jolly Nature  
- Dragon Dance  
- Earthquake  
- Scale Shot  
- Fire Punch`;

const result = validatePokemon(validPokemon);
console.log('Valid Pokemon test:', result.valid ? 'PASSED' : `FAILED: ${result.error}`);

// Test incomplete Pokemon
const invalidPokemon = `Flygon @ Loaded Dice  
Ability: Levitate  
- Dragon Dance`;

const result2 = validatePokemon(invalidPokemon);
console.log('Invalid Pokemon test:', result2.valid ? 'UNEXPECTED PASS' : `CORRECTLY FAILED: ${result2.error}`);

// Test format prompt generation
console.log('\n3. Testing format prompt generation:');
const ouPrompt = getFormatPrompt('ou');
console.log('OU format prompt:');
console.log(ouPrompt);

console.log('\n4. Testing team validation:');
const sampleTeam = `Flygon @ Loaded Dice  
Ability: Levitate  
Tera Type: Fire  
EVs: 248 Atk / 6 SpD / 252 Spe  
Jolly Nature  
- Dragon Dance  
- Earthquake  
- Scale Shot  
- Fire Punch  

Galvantula @ Focus Sash  
Ability: Compound Eyes  
Tera Type: Ghost  
EVs: 2 HP / 252 SpA / 252 Spe  
Timid Nature  
IVs: 0 Atk  
- Sticky Web  
- Thunder  
- Bug Buzz  
- Thunder Wave`;

// This is only 2 Pokemon, should fail
const teamResult = validateTeam(sampleTeam);
console.log('2-Pokemon team test (should fail):', teamResult.valid ? 'UNEXPECTED PASS' : `CORRECTLY FAILED: ${teamResult.error}`);

console.log('\nAll tests completed!');