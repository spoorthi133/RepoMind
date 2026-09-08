import { RepoWorkspace } from "./components/RepoWorkspace";
import { Sidebar } from "./components/Sidebar";
import { useRepos } from "./hooks/useRepos";

function App() {
  const { repos, selectedRepo, selectedId, setSelectedId, addRepo, removeRepo, adding, addError } = useRepos();

  return (
    <div className="app">
      <Sidebar
        repos={repos}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onAdd={addRepo}
        onRemove={removeRepo}
        adding={adding}
        addError={addError}
      />
      <main className="main">
        {selectedRepo ? (
          <RepoWorkspace repo={selectedRepo} />
        ) : (
          <div className="workspace-status">
            <p className="muted">Add a repo URL to get started.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
