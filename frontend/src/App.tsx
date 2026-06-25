// Three-panel shell placeholder. Panels are filled in M6–M9.
export default function App() {
  return (
    <div className="grid h-full grid-cols-[260px_1fr_400px] divide-x divide-gray-200">
      <aside className="overflow-y-auto bg-gray-50 p-4">
        <h1 className="text-brand text-lg font-semibold">TruBoard Policies</h1>
        <p className="mt-2 text-sm text-gray-500">Sidebar — policy list (M7)</p>
      </aside>

      <main className="overflow-y-auto p-4">
        <p className="text-sm text-gray-500">PDF viewer (M7)</p>
      </main>

      <section className="flex flex-col bg-gray-50 p-4">
        <p className="text-sm text-gray-500">Chatbot (M8)</p>
      </section>
    </div>
  )
}
