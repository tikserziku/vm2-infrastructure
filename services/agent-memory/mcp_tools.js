// MCP Memory Tools - добавить в mcp-hub/server.js

const { execSync } = require('child_process');
const path = require('path');

const MEMORY_SCRIPT = path.join(process.env.HOME, 'agent-memory', 'memory_agent.py');

function runMemoryCmd(args) {
    try {
        const result = execSync(`python3 ${MEMORY_SCRIPT} ${args}`, { encoding: 'utf8' });
        return JSON.parse(result);
    } catch (e) {
        return { error: e.message, stdout: e.stdout };
    }
}

// Tools to export
const memoryTools = {
    // Поиск в памяти агента
    agent_memory_search: {
        description: "Search agent memory for knowledge, paths, configs",
        parameters: {
            type: "object",
            properties: {
                query: { type: "string", description: "Search query" }
            },
            required: ["query"]
        },
        handler: async ({ query }) => runMemoryCmd(`search "${query}"`)
    },
    
    // Быстрый поиск пути
    agent_get_path: {
        description: "Quick lookup for file/folder path",
        parameters: {
            type: "object",
            properties: {
                what: { type: "string", description: "What to find (e.g., 'portfolio', 'secrets')" }
            },
            required: ["what"]
        },
        handler: async ({ what }) => {
            const result = execSync(`python3 ${MEMORY_SCRIPT} path "${what}"`, { encoding: 'utf8' });
            return { path: result.trim() };
        }
    },
    
    // Добавить знание
    agent_learn: {
        description: "Add knowledge to agent memory",
        parameters: {
            type: "object",
            properties: {
                category: { type: "string", description: "Category (paths, services, secrets, etc.)" },
                key: { type: "string", description: "Key name" },
                value: { type: "string", description: "Value" }
            },
            required: ["category", "key", "value"]
        },
        handler: async ({ category, key, value }) => runMemoryCmd(`add "${category}" "${key}" "${value}"`)
    },
    
    // История операций
    agent_history: {
        description: "Get operation history",
        parameters: {
            type: "object",
            properties: {
                limit: { type: "number", default: 10 }
            }
        },
        handler: async ({ limit = 10 }) => runMemoryCmd(`history ${limit}`)
    },
    
    // Сводка
    agent_memory_status: {
        description: "Get agent memory summary",
        parameters: { type: "object", properties: {} },
        handler: async () => runMemoryCmd('summary')
    }
};

module.exports = { memoryTools };
