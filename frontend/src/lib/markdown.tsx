/** Shared react-markdown component overrides (cyberpunk theme). */

export const markdownComponents = {
  a: (props: any) => (
    <a {...props} target="_blank" rel="noopener noreferrer"
       className="text-cyber-cyan underline hover:text-cyan-300" />
  ),
  table: (props: any) => (
    <div className="overflow-x-auto">
      <table {...props} className="my-4 w-full border-collapse text-sm" />
    </div>
  ),
  th: (props: any) => (
    <th {...props} className="border border-gray-700 bg-surface px-2 py-1 text-left text-cyber-cyan" />
  ),
  td: (props: any) => <td {...props} className="border border-gray-800 px-2 py-1" />,
  h1: (props: any) => <h1 {...props} className="mt-6 text-2xl font-bold text-cyber-cyan" />,
  h2: (props: any) => <h2 {...props} className="mt-5 text-xl font-bold text-gray-100" />,
  h3: (props: any) => <h3 {...props} className="mt-4 text-lg font-bold text-gray-200" />,
  ul: (props: any) => <ul {...props} className="my-2 list-disc pl-6" />,
  ol: (props: any) => <ol {...props} className="my-2 list-decimal pl-6" />,
  p: (props: any) => <p {...props} className="my-2 leading-relaxed" />,
  em: (props: any) => <em {...props} className="text-cyber-magenta" />,
};
