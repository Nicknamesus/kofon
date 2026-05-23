## General
1. We need to figure out the transition between the agent and the human salesmen. The current best is to make a human take over the chat. For this we need to make the user have an account, which is 2.

2. We need to add an account system (as Kofon doesn't have one yet). The bot should suggest to the useer to make an account. It's important that the chat isn't lost before user creates the account. 
What we could do is the agent gives the link to the sign in page, the user makes an account and continues the conversation. For this to work it's important that the system and the agent updates fast.

3. We need to ask for the specs more. For example even when the "3 best products" or the "best product family comes up" there needs to be some text at the bottom asking for specific specs so that if the user has them they can find the product faster.

4. We need to make explanations for all the product specs. Even though it's B2B, it's important that the agent can explain concepts like backlash and give (for example) the company's resume/description so that all users are satisfied. To ensure that the info is correct it would be ideal to have pre-written explanations.
Big question: When I asked it about backlash, it answered me correctly even though from my knowledge it has no files about it. Was that just DeepSeek's answer?

5. We need to balance the precision of answer's and the speed at which they are given. It's better to have an answer that doesn't give all the details right away but is served in 5 secs than a complete answer that takes 30 secs to generate. But normally the fact the agent uses an algorithm should more-or-less fix this problem because it greatly reduces the amount of data the agent needs to scan before answering.
Staying in the same topic, we need to balance readability and detail. We tested Neugart's chatbot, and it's answers have a lot of detail, but they have so much of it we got lost (plus it was slow). We need to make sure the agent's messages don't bore the user with too much detail, but also not so little the answers are useless.

6. The analysis needs to classify customers by priority (but for that we also kinda need Kofon to explain to us what they consider high-priority customers).

7. We need to make sure the customer understands the agent's capabilities correctly and doesn't over or under-estimate them.

8. We can make a customisation widget with entry fields that can either be filled or not, that way if a customer want to customise something they just fill in the fields and send it to an engineer, who gets structured data of what the customer wants and not just a vague description.

## Security
1. We need to prevent sensitive data leakage. Kofon defines what is sensitive and what is not, and we need to make sure nothing sensitive gets out there. There are 2 ways for this: give the agent no tasks/capabilities that require sensitive data or make sure the agent doesn't have direct access to it.

2. In the same vein, we need to protect ourselves from prompt injections

3. We need to clarify the data usage policy, since we plan on analysing conversations

4. DeepSeek is a big hole in all of this, because if the agent has access to any sensitive data at all, then deepseek might also have access to it through the llm calls.

## Maintenace
1. We need to make a manual for this agent so that other people can maintain it without us.
2. We need to make templates for the main file categories so that other people can add to/modify the database.

## Misc
- We need to stress test/ estimate to know how much traffic our agent can bear.
- How is our product exlusive and uncopiable by others
- We need to clarify how we'll analyse conversations.

## Testing Required
- Conversation conversion
- time saved
- time it will take for kofon to see results