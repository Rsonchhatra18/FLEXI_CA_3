import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// react-markdown never renders raw HTML, so LLM output can't inject markup.
const components = {
  a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
}

export default function Markdown({ children }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children || ''}
      </ReactMarkdown>
    </div>
  )
}
