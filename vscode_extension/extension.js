const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');
const path = require('path');

let client;

function getServerOptions() {
    // The extension is installed at ~/.vscode/extensions/taipan-2.0.0/
    // The LSP server is at <project_root>/lsp/server.py
    const extPath = path.dirname(__dirname);
    const projectRoot = path.resolve(extPath, '..');
    const serverPath = path.join(projectRoot, 'lsp', 'server.py');

    const python = process.platform === 'win32' ? 'py' : 'python3';

    return {
        command: python,
        args: ['-u', serverPath],
        options: { cwd: projectRoot }
    };
}

function startClient() {
    const serverOptions = getServerOptions();
    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'taipan' }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*.tp')
        }
    };

    client = new LanguageClient(
        'taipan-lsp',
        'taipan Language Server',
        serverOptions,
        clientOptions
    );

    client.start();
    vscode.window.showInformationMessage('taipan Language Server started');
}

function activate(context) {
    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('taipan.runFile', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor || editor.document.languageId !== 'taipan') {
                vscode.window.showWarningMessage('No taipan file is active');
                return;
            }
            const filePath = editor.document.fileName;
            const terminal = vscode.window.createTerminal('taipan Run');
            terminal.sendText(`cd "${path.dirname(filePath)}" && tai run "${path.basename(filePath)}"`);
            terminal.show();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('taipan.openRepl', () => {
            const terminal = vscode.window.createTerminal('taipan REPL');
            terminal.sendText('tai repl');
            terminal.show();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('taipan.restartServer', () => {
            if (client) {
                client.stop().then(() => {
                    startClient();
                });
            } else {
                startClient();
            }
        })
    );

    startClient();
}

function deactivate() {
    if (client) {
        return client.stop();
    }
    return undefined;
}

module.exports = { activate, deactivate };
