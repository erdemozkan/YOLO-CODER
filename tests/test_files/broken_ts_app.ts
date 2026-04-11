import * as fs from 'fs';

// Error 1: Missing Module Import
import { fakeHelper } from 'non_existent_ts_module';

interface User {
    id: number;
    name: string;
    isActive: boolean;
}

// Error 2: Type Error (String assigned to Number)
const activeUser: User = {
    id: "101",
    name: "Erdem",
    isActive: true
};

// Error 3: Syntax Error (Missing curly braces for function body)
function displayUser(u: User)
console.log(`User: ${u.name} (ID: ${u.id})`);

// Error 4: Runtime File Error
function loadSettings() {
    const rawData = fs.readFileSync('missing_ts_settings.json', 'utf8');
    return JSON.parse(rawData);
}

// Error 5: Undefined Variable
function executeLogic() {
    console.log("Executing payload...");
    console.log(uninitialized_ts_variable);
}

function main() {
    console.log("Booting up TypeScript Broken App...");
    displayUser(activeUser);

    const settings = loadSettings();
    console.log("Settings loaded:", settings);

    executeLogic();
}

main();
